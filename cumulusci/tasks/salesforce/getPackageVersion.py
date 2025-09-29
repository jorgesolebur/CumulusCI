from cumulusci.core.config.util import get_devhub_config
from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.core.tasks import BaseTask
from cumulusci.core.versions import PackageType, PackageVersionNumber
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.utils.options import CCIOptions, Field


class GetPackageVersion(BaseTask):
    """Custom task to get package version ID"""

    class Options(CCIOptions):
        package_name: str = Field(
            ..., description="Package name to get package version ID for."
        )
        package_version: str = Field(
            ..., description="Package version to get package version ID for."
        )
        prefix: str = Field(
            "",
            description="Prefix to add to the package name.",
        )
        suffix: str = Field(
            "",
            description="Suffix to add to the package name.",
        )
        fail_on_error: bool = Field(
            False, description="Fail on error. [default to False]"
        )

    parsed_options: Options

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.parsed_options.package_version = PackageVersionNumber.parse(
            self.parsed_options.package_version, package_type=PackageType.SECOND_GEN
        )

    def _init_task(self):
        self.tooling = get_simple_salesforce_connection(
            self.project_config,
            get_devhub_config(self.project_config),
            api_version=self.project_config.project__package__api_version,
            base_url="tooling",
        )

    def _run_task(self):
        package_name = f"{self.parsed_options.prefix}{self.parsed_options.package_name}{self.parsed_options.suffix}".strip()

        query = (
            f"SELECT Id, SubscriberPackageVersionId FROM Package2Version WHERE Package2.Name='{package_name}' AND "
            f"MajorVersion={self.parsed_options.package_version.MajorVersion} AND "
            f"MinorVersion={self.parsed_options.package_version.MinorVersion} AND "
            f"PatchVersion={self.parsed_options.package_version.PatchVersion} AND "
            f"BuildNumber={self.parsed_options.package_version.BuildNumber}"
        )

        res = self.tooling.query(query)
        if res["size"] == 0:
            msg = f"Package version {package_name} {self.parsed_options.package_version} not found"
            self.logger.warning(msg)
            if self.parsed_options.fail_on_error:
                raise SalesforceDXException(msg)
            return

        if res["size"] > 1:
            msg = f"Multiple package versions found for {package_name} {self.parsed_options.package_version}"
            self.logger.warning(msg)
            if self.parsed_options.fail_on_error:
                raise SalesforceDXException(msg)

        self.return_values["package_version_id"] = res["records"][0]["Id"]
        self.return_values["subscriber_package_version_id"] = res["records"][0][
            "SubscriberPackageVersionId"
        ]
        self.return_values["package_name"] = package_name
        self.return_values["package_version"] = self.parsed_options.package_version

        self.logger.info(
            f"Package version {package_name} {self.parsed_options.package_version} found"
        )
        self.logger.info(
            f"Package version id: {self.return_values['package_version_id']}"
        )
        self.logger.info(
            f"SubscriberPackageVersion Id: {self.return_values['subscriber_package_version_id']}"
        )

        return self.return_values
