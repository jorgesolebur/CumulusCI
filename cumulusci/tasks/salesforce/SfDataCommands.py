import json

import sarge

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.core.sfdx import sfdx
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class SfDataCommands(BaseSalesforceApiTask):
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
        self.data_command = "data "
        super()._init_options(kwargs)
        if self.parsed_options.flags_dir:
            self.args.extend(["--flags-dir ", self.parsed_options.flags_dir])
        if self.parsed_options.json_output:
            self.args.extend(["--json"])
        if self.parsed_options.api_version:
            self.args.extend(["--api_version", self.parsed_options.api_version])

    def _run_task(self):
        self.return_values = {}

        self.p: sarge.Command = sfdx(
            self.data_command,
            log_note="Running data command",
            args=self.args,
            check_return=True,
            username=self.org_config.username,
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
                f"Failed to parse the output of the {self.data_command} command"
            )


class SfDataToolingAPISupportedCommands(SfDataCommands):
    class Options(SfDataCommands.Options):
        use_tooling_api: bool = Field(
            None,
            description="Use Tooling API so you can run queries on Tooling API objects.",
        )


class DataQueryTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        query: str = Field(None, description="SOQL query to execute")
        file: str = Field(None, description="File that contains the SOQL query")
        all_rows: bool = Field(
            None,
            description="Include deleted records. By default, deleted records are not returned.",
        )
        result_format: str = Field(
            None,
            description="Format to display the results; the --json_output flag overrides this flag. Permissible values are: human, csv, json.",
        )
        output_file: str = Field(
            None,
            description="File where records are written; only CSV and JSON output formats are supported.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "query"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.query:
            self.args.extend(["--query", self.parsed_options.query])
        if self.parsed_options.file:
            self.args.extend(["--file", self.parsed_options.file])
        if self.parsed_options.all_rows:
            self.args.extend(["--all-rows", self.parsed_options.all_rows])
        if self.parsed_options.result_format:
            self.args.extend(["--result-format", self.parsed_options.result_format])
        if self.parsed_options.output_file:
            self.args.extend(["--output-file", self.parsed_options.output_file])

    def _run_task(self):
        super()._run_task()

        if self.parsed_options.json_output:
            self.logger.info(self.return_values)


class DataCreateRecordTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        sobject: str = Field(
            ...,
            description="API name of the Salesforce or Tooling API object that you're inserting a record into.",
        )
        values: str = Field(
            ...,
            description="Values for the flags in the form <fieldName>=<value>, separate multiple pairs with spaces.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "create record"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.options.get("sobject"):
            self.args.extend(["--sobject", self.options.get("sobject")])
        if self.options.get("values"):
            self.args.extend(["--values", self.options.get("values")])

    def _run_task(self):
        return super()._run_task()


class DataDeleteRecordTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        sobject: str = Field(
            ...,
            description="API name of the Salesforce or Tooling API object that you're deleting a record from.",
        )
        record_id: str = Field(None, description="ID of the record you’re deleting.")
        where: str = Field(
            None,
            description="List of <fieldName>=<value> pairs that identify the record you want to delete.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "delete record"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.options.get("sobject"):
            self.args.extend(["--sobject", self.options.get("sobject")])
        if self.options.get("record_id"):
            self.args.extend(["--record-id", self.options.get("record_id")])
        if self.options.get("where"):
            self.args.extend(["--where", self.options.get("where")])

    def _run_task(self):
        return super()._run_task()
