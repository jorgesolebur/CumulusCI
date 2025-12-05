from cumulusci.core.exceptions import SalesforceException
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field, MappingOption


class InsertRecord(BaseSalesforceApiTask):
    task_docs = """
        For example:

        cci task run insert_record --org dev -o object PermissionSet -o values Name:HardDelete,PermissionsBulkApiHardDelete:true
    """

    class Options(CCIOptions):
        object: str = Field(..., description="An sObject type to insert")
        values: MappingOption = Field(
            ...,
            description="Field names and values in the format 'aa:bb,cc:dd', or a YAML dict in cumulusci.yml.",
        )
        tooling: bool = Field(
            False, description="If True, use the Tooling API instead of REST API."
        )

    parsed_options: Options

    def _run_task(self):
        api = self.sf if not self.parsed_options.tooling else self.tooling
        object_handler = getattr(api, self.parsed_options.object)

        rc = object_handler.create(self.parsed_options.values)
        if rc["success"]:
            self.logger.info(
                f"{self.parsed_options.object} record inserted: {rc['id']}"
            )
        else:
            # this will probably never execute, due to simple_salesforce throwing
            # an exception, but just in case:
            raise SalesforceException(
                f"Could not insert {self.parsed_options.object} record : {rc['errors']}"
            )
