import os
from typing import Optional

from pydantic.v1 import root_validator

from cumulusci.core.exceptions import SalesforceException
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field, MappingOption


class UpdateRecord(BaseSalesforceApiTask):
    task_docs = """
        Update one or more Salesforce records.
        For example, update by record ID:
        cci task run update_record --org dev --object Account --record_id 001xx000003DGbXXXX --values Name:UpdatedName,Status__c:Active
        Or update by query criteria:
        cci task run update_record --org dev --object Account --where Name:TestAccount,Status__c:Draft --values Name:UpdatedName,Status__c:Active
        Or use environment variables with transform_values:
        cci task run update_record --org dev --object Account --record_id 001xx000003DGbXXXX --transform_values Name:ACCOUNT_NAME_VAR,Status__c:ACCOUNT_STATUS_VAR
    """

    class Options(CCIOptions):
        object: str = Field(..., description="An sObject type to update")
        values: Optional[MappingOption] = Field(
            None,
            description="Field names and values to update in the format 'aa:bb,cc:dd', or a YAML dict in cumulusci.yml.",
        )
        transform_values: Optional[MappingOption] = Field(
            None,
            description="Field names and environment variable keys in the format 'field:ENV_KEY,field2:ENV_KEY2'. Values will be extracted from environment variables.",
        )
        record_id: Optional[str] = Field(
            None,
            description="The ID of a specific record to update. If specified, the 'where' option is ignored.",
        )
        where: Optional[str] = Field(
            None,
            description="Query criteria to identify records in the format 'field:value,field2:value2'. Multiple records may be updated.",
        )
        tooling: bool = Field(
            False, description="If True, use the Tooling API instead of REST API."
        )
        fail_on_error: bool = Field(
            True,
            description="If True (default), fail the task if any record update fails. If False, log errors but continue.",
        )

        @root_validator
        def validate_options(cls, values):
            """Validate required option combinations"""
            # Validate that either record_id or where is provided
            if not values.get("record_id") and not values.get("where"):
                raise SalesforceException(
                    "Either 'record_id' or 'where' option must be specified"
                )

            # Validate that at least values or transform_values is provided
            if not values.get("values") and not values.get("transform_values"):
                raise SalesforceException(
                    "Either 'values' or 'transform_values' option must be specified"
                )

            return values

    parsed_options: Options

    def _init_task(self):
        super()._init_task()
        self.api = self.sf if not self.parsed_options.tooling else self.tooling

        # Build the final values dict by merging values and transform_values
        self.final_values = {}

        # Start with regular values if provided
        if self.parsed_options.values:
            self.final_values.update(self.parsed_options.values)

        # Process transform_values and extract from environment
        if self.parsed_options.transform_values:
            for field, env_key in self.parsed_options.transform_values.items():
                env_value = os.environ.get(env_key, env_key)
                self.final_values[field] = env_value
                self.logger.info(
                    f"Transform value for field '{field}': {env_key} -> {env_value}"
                )

    def _run_task(self):
        if self.parsed_options.record_id:
            # Direct update by record ID
            self._update_by_id(self.parsed_options.record_id)
        else:
            # Query and update multiple records
            self._update_by_query()

    def _update_by_id(self, record_id):
        """Update a single record by ID"""
        object_handler = getattr(self.api, self.parsed_options.object)

        try:
            rc = object_handler.update(record_id, self.final_values)
            if rc == 204 or (isinstance(rc, dict) and rc.get("success")):
                self.logger.info(
                    f"{self.parsed_options.object} record updated successfully: {record_id}"
                )
            else:
                error_msg = (
                    f"Could not update {self.parsed_options.object} record {record_id}"
                )
                if isinstance(rc, dict) and "errors" in rc:
                    error_msg += f": {rc['errors']}"
                if self.parsed_options.fail_on_error:
                    raise SalesforceException(error_msg)
                else:
                    self.logger.error(error_msg)
        except Exception as e:
            if self.parsed_options.fail_on_error:
                raise SalesforceException(
                    f"Error updating {self.parsed_options.object} record {record_id}: {str(e)}"
                )
            else:
                self.logger.error(
                    f"Error updating {self.parsed_options.object} record {record_id}: {str(e)}"
                )

    def _update_by_query(self):
        """Query records and update all matching records"""
        # Parse where clause into query criteria - MappingOption already parses it
        from cumulusci.core.utils import parse_list_of_pairs_dict_arg

        where_criteria = parse_list_of_pairs_dict_arg(self.parsed_options.where)

        # Build WHERE clause
        where_parts = [
            f"{field} = '{value}'" for field, value in where_criteria.items()
        ]
        where_clause = " AND ".join(where_parts)

        # Build and execute query
        query = f"SELECT Id FROM {self.parsed_options.object} WHERE {where_clause}"
        self.logger.info(f"Querying records: {query}")

        try:
            result = self.api.query(query)
        except Exception as e:
            raise SalesforceException(f"Error executing query: {str(e)}")

        records = result.get("records", [])
        total_count = len(records)

        if total_count == 0:
            self.logger.warning(
                f"No {self.parsed_options.object} records found matching criteria: {self.parsed_options.where}"
            )
            return

        self.logger.info(
            f"Found {total_count} {self.parsed_options.object} record(s) to update"
        )

        # Use different update strategy based on record count
        if total_count == 1:
            # Single record: use direct update
            self._update_by_id(records[0]["Id"])
        else:
            # Multiple records: use bulk update
            self._update_records_bulk(records)

    def _update_records_bulk(self, records):
        """Update multiple records using Bulk API"""
        # Prepare data for bulk update
        update_data = []
        for record in records:
            record_data = {"Id": record["Id"]}
            record_data.update(self.final_values)
            update_data.append(record_data)

        self.logger.info(
            f"Performing bulk update of {len(update_data)} {self.parsed_options.object} records"
        )

        try:
            # Use Bulk API for update
            results = self.bulk.update(self.parsed_options.object, update_data)

            # Process results
            success_count = 0
            failed_records = []

            for idx, result in enumerate(results):
                record_id = update_data[idx]["Id"]
                if result.success:
                    success_count += 1
                    self.logger.info(f"Updated record: {record_id}")
                else:
                    error_msg = f"Failed to update record {record_id}: {result.error}"
                    failed_records.append({"id": record_id, "error": result.error})
                    self.logger.error(error_msg)

            # Summary logging
            self.logger.info(
                f"Bulk update complete: {success_count}/{len(update_data)} records updated successfully"
            )

            # Handle failures
            if failed_records and self.parsed_options.fail_on_error:
                error_summary = "\n".join(
                    [f"  - {rec['id']}: {rec['error']}" for rec in failed_records]
                )
                raise SalesforceException(
                    f"Failed to update {len(failed_records)} record(s):\n{error_summary}"
                )

        except Exception as e:
            if self.parsed_options.fail_on_error:
                raise SalesforceException(f"Bulk update failed: {str(e)}")
            else:
                self.logger.error(f"Bulk update failed: {str(e)}")
