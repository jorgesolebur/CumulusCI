import json

import sarge

from cumulusci.core.config.util import get_devhub_config
from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.core.sfdx import sfdx
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class SfPackageCommands(BaseSalesforceApiTask):
    class Options(CCIOptions):
        json_output: bool = Field(
            None, description="Whether to return the result as a JSON object"
        )
        api_version: str = Field(None, description="API version to use for the command")
        flags_dir: str = Field(None, description="Import flag values from a directory")

    parsed_options: Options

    def _init_task(self):
        super()._init_task()

    def _init_options(self, kwargs):
        self.args = []
        self.package_command = "package "
        super()._init_options(kwargs)
        if self.parsed_options.flags_dir:
            self.args.extend(["--flags-dir", self.parsed_options.flags_dir])
        if self.parsed_options.json_output:
            self.args.extend(["--json"])
        if self.parsed_options.api_version:
            self.args.extend(["--api-version", self.parsed_options.api_version])

        devHubConfig = get_devhub_config(self.project_config)
        self.args.extend(["--target-dev-hub", devHubConfig.username])

    def _run_task(self):
        self.return_values = {}

        self.p: sarge.Command = sfdx(
            self.package_command,
            log_note="Running package command",
            args=self.args,
            check_return=True,
        )

        if self.parsed_options.json_output:
            self.return_values = self._load_json_output(self.p)

        for line in self.p.stdout_text:
            self.logger.info(line)

        for line in self.p.stderr_text:
            self.logger.error(line)

    def _load_json_output(self, p: sarge.Command, stdout: str = None):
        try:
            stdout = stdout or p.stdout_text.read()
            return json.loads(stdout)
        except json.decoder.JSONDecodeError:
            raise SalesforceDXException(
                f"Failed to parse the output of the {self.package_command} command"
            )


class PackageVersionUpdateTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_id: str = Field(
            ..., description="Package ID (04t..) or alias to update"
        )
        version_name: str = Field(None, description="New package version name")
        version_description: str = Field(
            None, description="New package version description"
        )
        branch: str = Field(None, description="New package version branch")
        tag: str = Field(None, description="New package version tag")
        installation_key: str = Field(
            None, description="New installation key for key-protected package"
        )

    def _init_task(self):
        super()._init_task()
        self.package_command += "version update"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_id:
            self.args.extend(["--package", self.parsed_options.package_id])
        if self.parsed_options.version_name:
            self.args.extend(["--version-name", self.parsed_options.version_name])
        if self.parsed_options.version_description:
            self.args.extend(
                ["--version-description", self.parsed_options.version_description]
            )
        if self.parsed_options.branch:
            self.args.extend(["--branch", self.parsed_options.branch])
        if self.parsed_options.tag:
            self.args.extend(["--tag", self.parsed_options.tag])
        if self.parsed_options.installation_key:
            self.args.extend(
                ["--installation-key", self.parsed_options.installation_key]
            )

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageVersionCreateTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_id: str = Field(
            ..., description="Package ID or alias to create version for"
        )
        version_name: str = Field(None, description="Package version name")
        version_description: str = Field(
            None, description="Package version description"
        )
        branch: str = Field(None, description="Package version branch")
        tag: str = Field(None, description="Package version tag")
        installation_key: str = Field(
            None, description="Installation key for key-protected package"
        )
        wait: int = Field(
            None, description="Number of minutes to wait for the command to complete"
        )
        code_coverage: bool = Field(
            None, description="Calculate code coverage for the package version"
        )
        skip_validation: bool = Field(
            None, description="Skip validation of the package version"
        )

    def _init_task(self):
        super()._init_task()
        self.package_command += "version create"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_id:
            self.args.extend(["--package", self.parsed_options.package_id])
        if self.parsed_options.version_name:
            self.args.extend(["--version-name", self.parsed_options.version_name])
        if self.parsed_options.version_description:
            self.args.extend(
                ["--version-description", self.parsed_options.version_description]
            )
        if self.parsed_options.branch:
            self.args.extend(["--branch", self.parsed_options.branch])
        if self.parsed_options.tag:
            self.args.extend(["--tag", self.parsed_options.tag])
        if self.parsed_options.installation_key:
            self.args.extend(
                ["--installation-key", self.parsed_options.installation_key]
            )
        if self.parsed_options.wait:
            self.args.extend(["--wait", str(self.parsed_options.wait)])
        if self.parsed_options.code_coverage:
            self.args.extend(["--code-coverage", self.parsed_options.code_coverage])
        if self.parsed_options.skip_validation:
            self.args.extend(["--skip-validation", self.parsed_options.skip_validation])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageVersionListTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_id: str = Field(
            None, description="Package ID or alias to list versions for"
        )
        status: str = Field(
            None,
            description="Filter by package version status (Success, Error, InProgress, Queued)",
        )
        modified: bool = Field(None, description="Show only modified package versions")
        concise: bool = Field(
            None,
            description="Show only the package version ID, version number, and status",
        )

    def _init_task(self):
        super()._init_task()
        self.package_command += "version list"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_id:
            self.args.extend(["--package", self.parsed_options.package_id])
        if self.parsed_options.status:
            self.args.extend(["--status", self.parsed_options.status])
        if self.parsed_options.modified:
            self.args.extend(["--modified", self.parsed_options.modified])
        if self.parsed_options.concise:
            self.args.extend(["--concise", self.parsed_options.concise])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageVersionDisplayTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_version_id: str = Field(
            ..., description="Package version ID to display"
        )
        verbose: bool = Field(None, description="Show verbose output")

    def _init_task(self):
        super()._init_task()
        self.package_command += "version display"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_version_id:
            self.args.extend(
                ["--package-version-id", self.parsed_options.package_version_id]
            )
        if self.parsed_options.verbose:
            self.args.extend(["--verbose", self.parsed_options.verbose])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageVersionDeleteTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_version_id: str = Field(..., description="Package version ID to delete")
        no_prompt_flag: bool = Field(None, description="Don't prompt for confirmation")

    def _init_task(self):
        super()._init_task()
        self.package_command += "version delete"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_version_id:
            self.args.extend(
                ["--package-version-id", self.parsed_options.package_version_id]
            )
        if self.parsed_options.no_prompt_flag:
            self.args.extend(["--no-prompt", self.parsed_options.no_prompt_flag])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageVersionReportTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_version_id: str = Field(
            ..., description="Package version ID to generate report for"
        )
        code_coverage: bool = Field(None, description="Generate code coverage report")
        output_dir: str = Field(None, description="Directory to save the report")

    def _init_task(self):
        super()._init_task()
        self.package_command += "version report"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_version_id:
            self.args.extend(
                ["--package-version-id", self.parsed_options.package_version_id]
            )
        if self.parsed_options.code_coverage:
            self.args.extend(["--code-coverage", self.parsed_options.code_coverage])
        if self.parsed_options.output_dir:
            self.args.extend(["--output-dir", self.parsed_options.output_dir])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageCreateTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        name: str = Field(..., description="Package name")
        description: str = Field(None, description="Package description")
        package_type: str = Field(None, description="Package type (Managed, Unlocked)")
        path: str = Field(None, description="Path to the package directory")

    def _init_task(self):
        super()._init_task()
        self.package_command += "create"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.name:
            self.args.extend(["--name", self.parsed_options.name])
        if self.parsed_options.description:
            self.args.extend(["--description", self.parsed_options.description])
        if self.parsed_options.package_type:
            self.args.extend(["--package-type", self.parsed_options.package_type])
        if self.parsed_options.path:
            self.args.extend(["--path", self.parsed_options.path])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageListTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        concise: bool = Field(
            None, description="Show only the package ID, name, and type"
        )

    def _init_task(self):
        super()._init_task()
        self.package_command += "list"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.concise:
            self.args.extend(["--concise", self.parsed_options.concise])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class PackageDisplayTask(SfPackageCommands):
    class Options(SfPackageCommands.Options):
        package_id: str = Field(..., description="Package ID or alias to display")
        verbose: bool = Field(None, description="Show verbose output")

    def _init_task(self):
        super()._init_task()
        self.package_command += "display"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.package_id:
            self.args.extend(["--package-id", self.parsed_options.package_id])
        if self.parsed_options.verbose:
            self.args.extend(["--verbose", self.parsed_options.verbose])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)
