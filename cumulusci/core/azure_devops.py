import logging
import time

import azure.devops.v7_0.git as model
from azure.devops.connection import Connection
from azure.devops.exceptions import (
    AzureDevOpsAuthenticationError,
    AzureDevOpsServiceError,
)
from msrest.authentication import BasicAuthentication

from cumulusci.core.exceptions import ADOApiError, ADOApiNotFoundError, ADOException

logger = logging.getLogger(__name__)
client: model.GitClient = None
repo: model.GitRepository = None
project: model.TeamProjectReference = None


def validate_client_repo(func):
    """Create decorator that allows org_name to be an option or an argument"""

    def decorator(*args, **kwargs):
        if client is None:
            raise Exception("Git client is not defined.")

        if repo is None:
            raise Exception("Git repository is not defined.")

        return func(*args, **kwargs)

    return decorator


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


def get_repo(repo_name, project_name):
    if client is None:
        raise Exception("Git client is not defined.")

    try:
        return client.get_repository(repo_name, project_name)
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to get repo {repo_name}: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during for repo {repo_name}: {str(ex)}"
        raise Exception(message)


@validate_client_repo
def get_ref_for_tag(tag_name: str) -> model.GitRef:
    """Fetches a tag by name from the given repository"""
    if tag_name is None:
        raise ADOException("Source tag need to be specified.")

    refs: list = []
    try:
        refs = client.get_refs(
            repo.id,
            project.id,
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


@validate_client_repo
def get_tag_by_name(tag_name: str) -> model.GitAnnotatedTag:
    """Gets a Reference object for the tag with the given name"""
    ref = get_ref_for_tag(client, repo, tag_name)

    try:
        annotatedTag: model.GitAnnotatedTag = client.get_annotated_tag(
            project.id, repo.id, ref.object_id
        )

        if annotatedTag is None:
            raise ADOException("Tag not found error.")

        return annotatedTag
    except ADOException as e:
        logger.error(e)
        raise ADOApiNotFoundError(
            f"Could not find reference for 'tags/{tag_name}' on ADO. {e}"
        )


@validate_client_repo
def clone_tag(
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
        tag = client.create_annotated_tag(clone_tag, project.id, repo.id)
    except Exception as e:
        logger.error(f"Error: Clone tag {e}")
        raise ADOApiNotFoundError(f"Could not create tag {tag_name} on ADO.")

    if tag is None:
        raise ADOException("Tag creation failed.")

    return tag


@validate_client_repo
def validate_branch(branch):
    try:
        client.get_branch(repo.id, branch, project.id)
    except AzureDevOpsServiceError as e:
        e.message = f"Branch {branch} not found. {e.message}"
        raise AzureDevOpsServiceError(e)


@validate_client_repo
def get_commit_diffs(branch_name, commit):
    base_version_descriptor = model.GitBaseVersionDescriptor(
        commit, version_type="commit", base_version=commit, base_version_type="commit"
    )

    target_version_descriptor = model.GitTargetVersionDescriptor(
        branch_name,
        version_type="branch",
        target_version=branch_name,
        target_version_type="branch",
    )
    try:
        commit_diffs = client.get_commit_diffs(
            repo.id,
            project.id,
            top=10,
            base_version_descriptor=base_version_descriptor,
            target_version_descriptor=target_version_descriptor,
        )

        return commit_diffs
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to get commit diffs: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during getting commit diffs: {str(ex)}"
        raise Exception(message)


@validate_client_repo
def create_pull_request(
    source_branch,
    target_branch,
    title="Automated Pull Request",
    description="This pull request was created via CCI",
):
    try:
        pull_request = model.GitPullRequest(
            source_ref_name=f"refs/heads/{source_branch}",
            target_ref_name=f"refs/heads/{target_branch}",
            title=title,
            description=description,
        )

        created_pr = client.create_pull_request(
            git_pull_request_to_create=pull_request,
            repository_id=repo.id,
            project=project.id,
        )

        logger.info(
            f"Pull request created: #{created_pr.pull_request_id} - {created_pr.title}"
        )

        return created_pr
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to create pull request: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during PR creation: {str(ex)}"
        raise Exception(message)


@validate_client_repo
def update_pull_request(pull_request_id, git_pull_request_to_update):
    try:
        updated_pr = client.update_pull_request(
            git_pull_request_to_update=git_pull_request_to_update,
            repository_id=repo.id,
            pull_request_id=pull_request_id,
            project=project.id,
        )
        logger.info(f"Pull request #{updated_pr.pull_request_id} updated successfully.")
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to update pull request #{pull_request_id}: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during PR update: {str(ex)}"
        raise Exception(message)


@validate_client_repo
def get_pull_request(pull_request_id):
    try:
        # Check if the PR can be auto-merged
        pr = client.get_pull_request(
            repository_id=repo.id, pull_request_id=pull_request_id, project=project.id
        )
        return pr
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to get pull request status: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during PR status check: {ex.message}"
        raise Exception(message)


@validate_client_repo
def can_pr_auto_merged(pull_request_id, options={}):
    """
    Waits until the pull request has completed merge checks or timeout hits.
    """
    logger.debug("Waiting for PR auto-merge check...")
    start_time = time.time()
    timeout = options.get("retry_timeout", 100)
    interval = options.get("retry_interval", 10)

    while time.time() - start_time < timeout:
        pr = get_pull_request(pull_request_id)

        if pr.merge_status == "succeeded":
            logger.info("Pull request can be automatically merged.")
            return True

        if pr.merge_status in ("conflicts", "failure"):
            logger.info(f"Merge status resolved: {pr.merge_status}")
            return False

        logger.info(
            f"Current merge status: {pr.merge_status}. Retrying in {interval} seconds..."
        )
        time.sleep(interval)

    logger.warning(
        f"Pull request cannot be auto-merged. Merge status: {pr.merge_status}"
    )
    return False


@validate_client_repo
def merge_branch(source_branch, target_branch, options={}):
    created_pr = create_pull_request(source_branch, target_branch)
    pr = None
    if can_pr_auto_merged(created_pr.pull_request_id, options) is True:
        my_identity = created_pr.created_by
        # Set PR to auto-complete and bypass rules
        completion_options = model.GitPullRequestCompletionOptions(
            delete_source_branch=options.get(
                "completion_opts_delete_source_branch", False
            ),
            merge_strategy=options.get(
                "completion_opts_merge_strategy", "squash"
            ),  # 'noFastForward', 'rebase', 'rebaseMerge', etc.
            bypass_policy=options.get("completion_opts_bypass_policy", False),
            bypass_reason=options.get(
                "completion_opts_bypass_reason", "Automated bypass for CI/CD pipeline"
            ),
        )

        git_pull_request_to_update = model.GitPullRequest(
            auto_complete_set_by=my_identity, completion_options=completion_options
        )

        pr = update_pull_request(created_pr.pull_request_id, git_pull_request_to_update)

    elif not (options.get("create_pull_request_on_conflict")):
        git_pull_request_to_update = model.GitPullRequest(status="abandoned")
        pr = update_pull_request(created_pr.pull_request_id, git_pull_request_to_update)
    else:
        logger.info(f"Merge conflict on branch {target_branch}: Pull request created")
    return pr


@validate_client_repo
def get_branches(source_branch):
    try:
        base_version_descriptor = model.GitVersionDescriptor(
            source_branch, "none", "branch"
        )
        return client.get_branches(repo.id, project.id, base_version_descriptor)
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to get branches: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error when getting branches: {str(ex)}"
        raise Exception(message)


@validate_client_repo
def get_pull_requests(search_options, max_comment_length=None, skip=None, top=None):
    try:
        if search_options is None or len(search_options.keys()) < 1:
            top = 10

        search_criteria = model.GitPullRequestSearchCriteria(
            source_ref_name=search_options.get("source_ref_name"),
            status=search_options.get("status"),
            repository_id=repo.id,
        )
        return client.get_pull_requests(
            repo.id, search_criteria, project.id, max_comment_length, skip, top
        )
    except AzureDevOpsServiceError as e:
        e.message = f"Failed to get pull requests: {e.message}"
        raise AzureDevOpsServiceError(e)
    except Exception as ex:
        message = f"Unexpected error during getting pull requests: {str(ex)}"
        raise Exception(message)
