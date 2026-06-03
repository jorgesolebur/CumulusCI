from typing import Dict, Optional

from pydantic.v1 import root_validator

from cumulusci.core.exceptions import SalesforceException
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field, MappingOption


class FieldLookupOption(CCIOptions):
    """Defines a dynamic lookup to resolve a field value from another sObject."""

    field: str = Field(
        ...,
        description="The field to retrieve from the looked-up record (e.g., Id).",
    )
    object: str = Field(..., description="The sObject type to query.")
    where: str = Field(
        ...,
        description="A SOQL WHERE clause to identify the record (e.g., \"Name = 'Test'\").",
    )


class InsertRecord(BaseSalesforceApiTask):
    task_docs = """
        Insert a Salesforce record with optional dynamic field lookup resolution.

        Insert with static values:

        cci task run insert_record --org dev -o object PermissionSet -o values Name:HardDelete,PermissionsBulkApiHardDelete:true

        Insert with lookup values defined in cumulusci.yml:

        tasks:
          insert_contact:
            class_path: cumulusci.tasks.salesforce.InsertRecord
            options:
              object: Contact
              values:
                LastName: Smith
              lookupValues:
                AccountId:
                  field: Id
                  object: Account
                  where: "Name = 'Test Account'"

        Either 'values', 'lookupValues', or both must be provided.
    """

    class Options(CCIOptions):
        object: str = Field(..., description="An sObject type to insert.")
        values: Optional[MappingOption] = Field(
            None,
            description="Field names and values in the format 'aa:bb,cc:dd', or a YAML dict in cumulusci.yml.",
        )
        lookupValues: Optional[Dict[str, FieldLookupOption]] = Field(
            None,
            description=(
                "A YAML dict mapping target field names to lookup definitions. Each entry "
                "specifies the sObject, the field to retrieve, and a WHERE clause used to "
                "resolve the value at runtime. The first matching record is always used. "
                "Example:\n"
                "  lookupValues:\n"
                "    AccountId:\n"
                "      field: Id\n"
                "      object: Account\n"
                "      where: \"Name = 'Acme'\""
            ),
        )
        tooling: bool = Field(
            False, description="If True, use the Tooling API instead of REST API."
        )
        fail_on_multiple_records: bool = Field(
            False,
            description=(
                "If True, fail the task when a lookup query returns more than one record. "
                "If False (default), log a warning and use the first record found."
            ),
        )
        fail_on_error: bool = Field(
            True,
            description=(
                "If True (default), fail the task if the insert API call fails. "
                "If False, log a warning and continue without raising an exception."
            ),
        )

        @root_validator
        def validate_values_or_lookup(cls, values):
            if not values.get("values") and not values.get("lookupValues"):
                raise SalesforceException(
                    "Either 'values' or 'lookupValues' option must be specified."
                )
            return values

    parsed_options: Options

    def _resolve_lookup_values(self) -> dict:
        """Execute lookup queries and return a dict of {target_field: resolved_value}."""
        resolved = {}
        api = self.sf if not self.parsed_options.tooling else self.tooling

        for target_field, lookup in self.parsed_options.lookupValues.items():
            query = f"SELECT {lookup.field} FROM {lookup.object} WHERE {lookup.where}"
            self.logger.info(f"Resolving lookup for field '{target_field}': {query}")

            try:
                result = api.query(query)
            except Exception as e:
                raise SalesforceException(
                    f"Error executing lookup query for field '{target_field}': {str(e)}"
                )

            records = result.get("records", [])

            if not records:
                raise SalesforceException(
                    f"Lookup query for field '{target_field}' returned no records. Query: {query}"
                )

            if len(records) > 1:
                msg = f"Lookup query for field '{target_field}' returned {len(records)} records."
                if self.parsed_options.fail_on_multiple_records:
                    raise SalesforceException(msg)
                self.logger.warning(f"{msg} Using the first record found.")

            resolved_value = records[0][lookup.field]
            resolved[target_field] = resolved_value
            self.logger.info(
                f"Resolved lookup for field '{target_field}': {resolved_value}"
            )

        return resolved

    def _run_task(self):
        api = self.sf if not self.parsed_options.tooling else self.tooling
        object_handler = getattr(api, self.parsed_options.object)

        # Build the final payload by merging static values and resolved lookups
        final_values = {}

        if self.parsed_options.values:
            final_values.update(self.parsed_options.values)

        if self.parsed_options.lookupValues:
            resolved = self._resolve_lookup_values()
            final_values.update(resolved)

        try:
            rc = object_handler.create(final_values)
        except Exception as e:
            msg = f"Error inserting {self.parsed_options.object} record: {str(e)}"
            if self.parsed_options.fail_on_error:
                raise SalesforceException(msg)
            self.logger.warning(msg)
            return

        if rc["success"]:
            self.logger.info(
                f"{self.parsed_options.object} record inserted: {rc['id']}"
            )
        else:
            # simple_salesforce normally raises before reaching here, but handled defensively
            msg = (
                f"Could not insert {self.parsed_options.object} record: {rc['errors']}"
            )
            if self.parsed_options.fail_on_error:
                raise SalesforceException(msg)
            self.logger.warning(msg)
