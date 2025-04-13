import logging

import azure.devops.v7_0.git as model
from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsAuthenticationError
from msrest.authentication import BasicAuthentication

from cumulusci.core.exceptions import ADOApiError, ADOApiNotFoundError, ADOException

logger = logging.getLogger(__name__)


def validate_service(options: dict, keychain) -> dict:
    personal_access_token = options["token"]
    organization_url = options["organization_url"]

    services = keychain.get_services_for_type("azure_devops")
    if services:
        hosts = [service.organization_url for service in services]
        if hosts.count(organization_url) > 1:
            raise ADOException(
                f"More than one Azure Devops service configured for domain {organization_url}."
            )

    try:
        # Get a client (the "core" client provides access to projects, teams, etc)
        connection = _authenticate(personal_access_token, organization_url)
        core_client = connection.clients.get_core_client()
        base_url = core_client.config.base_url
        assert organization_url in base_url, f"https://{organization_url}"
    except AttributeError as e:
        raise ADOException(f"Authentication Error. ({str(e)})")
    except Exception as e:
        raise AzureDevOpsAuthenticationError(f"Authentication Error. ({str(e)})")

    return options


def _authenticate(token: str, org_url: str) -> Connection:
    organization_url = f"https://{org_url}"
    # Create a connection to the org
    credentials = BasicAuthentication("", token)
    connection = Connection(base_url=organization_url, creds=credentials)

    # Get a client (the "core" client provides access to projects, teams, etc)
    connection.authenticate()

    return connection


def get_azure_api_conntection(service_config, session=None):
    return _authenticate(service_config.token, service_config.organization_url)


def get_ref_for_tag(
    client: model.GitClient, repo: model.GitRepository, tag_name: str
) -> model.GitRef:
    """Fetches a tag by name from the given repository"""
    if tag_name is None:
        raise ADOException("Source tag need to be specified.")

    refs: list = []
    try:
        refs = client.get_refs(
            repo.id,
            repo.project.id,
            filter=f"tags/{tag_name}",
            include_statuses=True,
            latest_statuses_only=True,
            peel_tags=True,
        )
    except Exception as e:
        raise ADOException(f"Tag not found. Error {e}.")

    if len(refs) > 1:
        raise ADOApiError(f"More than one tag found for {tag_name}.")

    if len(refs) == 0:
        raise ADOApiError(f"Could not find tag {tag_name}.")

    ref = refs[0]

    if ref.peeled_object_id is None:
        msg = f"Could not find tag '{tag_name}' with SHA {ref.object_id} on ADO."
        msg += f"\n{tag_name} is not an annotated tag."
        raise ADOApiNotFoundError(msg)

    return ref


def get_tag_by_name(
    client: model.GitClient, repo: model.GitRepository, tag_name: str
) -> model.GitAnnotatedTag:
    """Gets a Reference object for the tag with the given name"""
    ref = get_ref_for_tag(client, repo, tag_name)

    try:
        annotatedTag: model.GitAnnotatedTag = client.get_annotated_tag(
            repo.project.id, repo.id, ref.object_id
        )

        if annotatedTag is None:
            raise ADOException("Tag not found error.")

        return annotatedTag
    except ADOException as e:
        logger.error(e)
        raise ADOApiNotFoundError(
            f"Could not find reference for 'tags/{tag_name}' on ADO. {e}"
        )


def clone_tag(
    client: model.GitClient,
    repo: model.GitRepository,
    src_tag: model.GitAnnotatedTag,
    tag_name: str,
    message: str = None,
):
    clone_tag = model.GitAnnotatedTag()
    clone_tag.message = (
        message if message is not None else f"Cloned from {src_tag.name}"
    )
    clone_tag.name = tag_name

    clone_tag.tagged_object = model.GitObject()
    clone_tag.tagged_object.object_id = src_tag.object_id

    tag: model.GitAnnotatedTag = None

    try:
        tag = client.create_annotated_tag(clone_tag, repo.project.id, repo.id)
    except Exception as e:
        logger.error(f"Error: Clone tag {e}")
        raise ADOApiNotFoundError(f"Could not create tag {tag_name} on ADO.")

    if tag is None:
        raise ADOException("Tag creation failed.")

    return tag
