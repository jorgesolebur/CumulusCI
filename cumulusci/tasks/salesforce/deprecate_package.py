from typing import Dict, List, Optional

import click
from simple_salesforce.exceptions import SalesforceMalformedRequest

from cumulusci.core.config.util import get_devhub_config
from cumulusci.core.exceptions import SalesforceException, TaskOptionsError
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class DeprecatePackage(BaseSalesforceApiTask):
    """
    Delete a Salesforce Package2 and its Package2Version records.

    Before deprecating, the following checks are performed:
    - The package must be in a dev hub org.
    - If Package2Version records exist, they will be deprecated first.
    - Cannot delete 2GP Managed packages that are released.
    """

    task_docs = """
    Delete a Salesforce Package2 (2GP package).

    The task will:
    1. Find the package by Id or Name, In the dev hub org if no org is specified.
    2. Delete all non-deprecated Package2Version records first
    3. Delete the Package2

    Cannot delete 2GP Managed packages that are released.

    Examples:
        # Delete by package Id
        cci task run delete_package --org devhub --package 0Ho000000000000AAA

        # Delete by package name
        cci task run delete_package --org devhub --package MyPackage

        # Delete without confirmation prompt
        cci task run delete_package --org devhub --package 0Ho000000000000AAA --no_prompt True
    """

    class Options(CCIOptions):
        package: str = Field(
            ...,
            description="The Package2 Id (0Ho...) or Name to delete",
        )

    parsed_options: Options

    # We do use a Salesforce org, but it's the dev hub obtained using get_devhub_config,
    # so the user does not need to specify an org on the CLI
    salesforce_task = False

    # Since we may override org_config, don't try to refresh its token in the default way
    def _update_credentials(self):
        if self.org_config:
            with self.org_config.save_if_changed():
                self.org_config.refresh_oauth_token(self.project_config.keychain)

    def _init_task(self):
        # If no org is specified, use devhub as default
        if not self.org_config:
            self.org_config = get_devhub_config(self.project_config)
        super()._init_task()

    def _run_task(self):
        """Main task execution"""
        # Get package information
        package_info = self._get_package(self.parsed_options.package)
        if not package_info:
            raise TaskOptionsError(f"Package '{self.parsed_options.package}' not found")

        package_id = package_info["Id"]
        package_name = package_info.get("Name", package_id)
        container_options = package_info.get("ContainerOptions", "")

        self.logger.info(
            f"Found package: {package_name} (Id: {package_id}, Type: {container_options})"
        )

        # Get all non-deleted package versions
        versions = self._get_package_versions(package_id)
        if versions:
            self.logger.info(f"Found {len(versions)} non-deleted version(s)")

            # Check if any versions cannot be deleted
            for version in versions:
                if not self._check_can_deprecate_version(version, container_options):
                    raise SalesforceException(
                        f"Cannot delete released Managed package version: {version.get('SubscriberPackageVersionId')}"
                    )

            # Prompt for confirmation
            if not getattr(click, "no_prompt", False):
                version_list = "\n".join(
                    [
                        f"  - {v.get('Id')} (v{v.get('MajorVersion')}.{v.get('MinorVersion')}.{v.get('PatchVersion')})"
                        for v in versions
                    ]
                )
                message = (
                    f"This will delete package '{package_name}' and {len(versions)} version(s):\n"
                    f"{version_list}\n"
                    f"Continue?"
                )
                if not click.confirm(message, default=False):
                    raise SalesforceException("Deprecation canceled by user")

            # Delete versions first
            self._deprecate_versions(versions)
        else:
            self.logger.info("No non-deprecated versions found")

            # Prompt for confirmation if no versions
            if not getattr(click, "no_prompt", False):
                message = f"This will delete package '{package_name}'.\n" f"Continue?"
                if not click.confirm(message, default=False):
                    raise SalesforceException("Deprecation canceled by user")

        # Check if package itself can be deprecated
        if not self._check_can_deprecate_package(package_info, versions):
            raise SalesforceException(
                f"Cannot delete released Managed package: {package_name}"
            )

        # Delete the package
        self._deprecate_package(package_id, package_name)

        self.logger.info(f"Successfully deprecated package: {package_name}")

    def _get_package(self, package_identifier: str) -> Optional[Dict]:
        """
        Get Package2 by Id or Name.

        @param package_identifier: Package2 Id (0Ho...) or Name
        @return: Package2 record dict or None if not found
        """
        # Check if package_identifier is an Id or Name
        if package_identifier.startswith("0Ho"):
            query = f"SELECT Id, Name, ContainerOptions, IsDeprecated FROM Package2 WHERE Id='{package_identifier}' AND IsDeprecated = FALSE"
        else:
            # Query by Name
            query = f"SELECT Id, Name, ContainerOptions, IsDeprecated FROM Package2 WHERE Name='{package_identifier}' AND IsDeprecated = FALSE"

        try:
            result = self.tooling.query(query)
            if result.get("size", 0) == 0:
                return None
            if result.get("size", 0) > 1:
                raise TaskOptionsError(
                    f"Multiple packages found with name '{package_identifier}'. Please use Package2 Id instead."
                )
            return result["records"][0]
        except SalesforceMalformedRequest as err:
            if "Object type 'Package2' is not supported" in err.content[0]["message"]:
                raise TaskOptionsError(
                    "This org does not have a Dev Hub with 2nd-generation packaging enabled."
                )
            raise  # pragma: no cover

    def _get_package_versions(self, package_id: str) -> List[Dict]:
        """
        Get all non-deprecated Package2Version records for a package.

        @param package_id: Package2 Id
        @return: List of Package2Version records
        """
        query = (
            f"SELECT Id, MajorVersion, MinorVersion, PatchVersion, "
            f"IsReleased, IsDeprecated, SubscriberPackageVersionId FROM Package2Version "
            f"WHERE Package2Id='{package_id}' AND IsDeprecated = FALSE"
        )

        try:
            result = self.tooling.query(query)
            return result.get("records", [])
        except SalesforceMalformedRequest as err:
            if "Object type 'Package2' is not supported" in err.content[0]["message"]:
                raise TaskOptionsError(
                    "This org does not have a Dev Hub with 2nd-generation packaging enabled."
                )
            raise  # pragma: no cover

    def _check_can_deprecate_version(
        self, version: Dict, container_options: str
    ) -> bool:
        """
        Check if a Package2Version can be deprecated.

        Cannot delete 2GP Managed packages that are released.

        @param version: Package2Version record dict
        @param container_options: ContainerOptions from Package2 (Managed/Unlocked)
        @return: True if can be deprecated, False otherwise
        """
        # Cannot delete released Managed packages
        if container_options == "Managed" and version.get("IsReleased", False):
            return False
        return True

    def _check_can_deprecate_package(
        self, package_info: Dict, versions: List[Dict]
    ) -> bool:
        """
        Check if a Package2 can be deprecated.

        Cannot delete if it's a Managed package with any released versions.

        @param package_info: Package2 record dict
        @param versions: List of Package2Version records (already filtered to non-deprecated)
        @return: True if can be deprecated, False otherwise
        """
        container_options = package_info.get("ContainerOptions", "")
        if container_options == "Managed":
            # Check if any versions are released
            for version in versions:
                if version.get("IsReleased", False):
                    return False
        return True

    def _deprecate_versions(self, versions: List[Dict]):
        """
        Delete all Package2Version records.

        @param versions: List of Package2Version records to deprecate
        """
        if not versions:
            return

        Package2Version = self._get_tooling_object("Package2Version")
        failed_versions = []

        for version in versions:
            version_id = version["Id"]
            subscriber_package_version_id = version["SubscriberPackageVersionId"]
            version_str = f"v{version.get('MajorVersion')}.{version.get('MinorVersion')}.{version.get('PatchVersion')}"
            try:
                Package2Version.update(version_id, {"IsDeprecated": True})
                self.logger.info(
                    f"Deleted Subscriber Package Version: {subscriber_package_version_id} ({version_str})"
                )
            except Exception as e:
                error_msg = f"Failed to delete Package2Version {subscriber_package_version_id}: {str(e)}"
                self.logger.error(error_msg)
                failed_versions.append({"id": version_id, "error": str(e)})

        if failed_versions:
            error_summary = "\n".join(
                [f"  - {v['id']}: {v['error']}" for v in failed_versions]
            )
            raise SalesforceException(
                f"Failed to delete {len(failed_versions)} Package2Version record(s):\n{error_summary}"
            )

    def _deprecate_package(self, package_id: str, package_name: str):
        """
        Delete a Package2 record.

        @param package_id: Package2 Id
        @param package_name: Package2 Name (for logging)
        """
        Package2 = self._get_tooling_object("Package2")
        try:
            Package2.update(package_id, {"IsDeprecated": True})
            self.logger.info(f"Deleted Package2: {package_id} ({package_name})")
        except Exception as e:
            raise SalesforceException(
                f"Failed to delete Package2 {package_id}: {str(e)}"
            )
