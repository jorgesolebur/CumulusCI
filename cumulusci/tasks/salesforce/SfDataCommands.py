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


class DataUpdateRecordTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        sobject: str = Field(
            ...,
            description="API name of the Salesforce or Tooling API object that you're updating a record from.",
        )
        record_id: str = Field(None, description="ID of the record you’re updating.")
        where: str = Field(
            None,
            description="List of <fieldName>=<value> pairs that identify the record you want to update.",
        )
        values: str = Field(
            ...,
            description="Values for the flags in the form <fieldName>=<value>, separate multiple pairs with spaces.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "update record"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.sobject:
            self.args.extend(["--sobject", self.parsed_options.sobject])
        if self.parsed_options.record_id:
            self.args.extend(["--record-id", self.parsed_options.record_id])
        if self.parsed_options.where:
            self.args.extend(["--where", self.parsed_options.where])
        if self.parsed_options.values:
            self.args.extend(["--values", self.parsed_options.values])

    def _run_task(self):
        return super()._run_task()


class DataGetRecordTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        sobject: str = Field(
            ...,
            description="API name of the Salesforce or Tooling API object that you're fetching a record from.",
        )
        record_id: str = Field(None, description="ID of the record you’re fetching.")
        where: str = Field(
            None,
            description="List of <fieldName>=<value> pairs that identify the record you want to fetch.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "get record"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.sobject:
            self.args.extend(["--sobject", self.parsed_options.sobject])
        if self.parsed_options.record_id:
            self.args.extend(["--record-id", self.parsed_options.record_id])
        if self.parsed_options.where:
            self.args.extend(["--where", self.parsed_options.where])

    def _run_task(self):
        return super()._run_task()


class DataQueryResumeTask(SfDataToolingAPISupportedCommands):
    class Options(SfDataToolingAPISupportedCommands.Options):
        bulk_query_id: str = Field(
            ...,
            description="The 18-character ID of the bulk query to resume.",
        )
        result_format: str = Field(
            None,
            description="Format to display the results; the --json_output flag overrides this flag. Permissible values are: human, csv, json.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "query resume"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.bulk_query_id:
            self.args.extend(["--bulk-query-id", self.parsed_options.bulk_query_id])
        if self.parsed_options.result_format:
            self.args.extend(["--result-format", self.parsed_options.result_format])

    def _run_task(self):
        return super()._run_task()


class DataDeleteBulkTask(SfDataCommands):
    class Options(SfDataCommands.Options):
        sobject: str = Field(
            ...,
            description="The API name of the object for the bulk job.",
        )
        file: str = Field(
            ...,
            description="The path to the CSV file that contains the IDs of the records to delete.",
        )
        wait: int = Field(
            None,
            description="The number of minutes to wait for the command to complete.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "delete bulk"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.sobject:
            self.args.extend(["--sobject", self.parsed_options.sobject])
        if self.parsed_options.file:
            self.args.extend(["--file", self.parsed_options.file])
        if self.parsed_options.wait:
            self.args.extend(["--wait", str(self.parsed_options.wait)])

    def _run_task(self):
        return super()._run_task()


class DataUpsertBulkTask(SfDataCommands):
    class Options(SfDataCommands.Options):
        sobject: str = Field(
            ...,
            description="The API name of the object for the bulk job.",
        )
        file: str = Field(
            ...,
            description="The path to the CSV file that contains the records to upsert.",
        )
        external_id_field: str = Field(
            ...,
            description="The API name of the external ID field for the upsert.",
        )
        wait: int = Field(
            None,
            description="The number of minutes to wait for the command to complete.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "upsert bulk"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.sobject:
            self.args.extend(["--sobject", self.parsed_options.sobject])
        if self.parsed_options.file:
            self.args.extend(["--file", self.parsed_options.file])
        if self.parsed_options.external_id_field:
            self.args.extend(
                ["--external-id-field", self.parsed_options.external_id_field]
            )
        if self.parsed_options.wait:
            self.args.extend(["--wait", str(self.parsed_options.wait)])

    def _run_task(self):
        return super()._run_task()


class DataImportTreeTask(SfDataCommands):
    class Options(SfDataCommands.Options):
        files: list = Field(
            None,
            description="A list of paths to sObject Tree API plan definition files.",
        )
        plan: str = Field(
            None,
            description="The path to a plan definition file.",
        )
        content_type_map: str = Field(
            None,
            description="A mapping of file extensions to content types.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "import tree"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.files:
            self.args.extend(["--files", ",".join(self.parsed_options.files)])
        if self.parsed_options.plan:
            self.args.extend(["--plan", self.parsed_options.plan])
        if self.parsed_options.content_type_map:
            self.args.extend(
                ["--content-type-map", self.parsed_options.content_type_map]
            )

    def _run_task(self):
        return super()._run_task()


class DataExportTreeTask(SfDataCommands):
    class Options(SfDataCommands.Options):
        query: str = Field(
            ...,
            description="A SOQL query that retrieves the records you want to export.",
        )
        plan: bool = Field(
            False,
            description="Generate a plan definition file.",
        )
        prefix: str = Field(
            None,
            description="The prefix for the exported data files.",
        )
        output_dir: str = Field(
            None,
            description="The directory to store the exported files.",
        )

    def _init_task(self):
        super()._init_task()
        self.data_command += "export tree"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        if self.parsed_options.query:
            self.args.extend(["--query", self.parsed_options.query])
        if self.parsed_options.plan:
            self.args.extend(["--plan"])
        if self.parsed_options.prefix:
            self.args.extend(["--prefix", self.parsed_options.prefix])
        if self.parsed_options.output_dir:
            self.args.extend(["--output-dir", self.parsed_options.output_dir])

    def _run_task(self):
        return super()._run_task()
