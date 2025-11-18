import json
from inspect import signature
from typing import Dict, List

from pydantic.v1 import create_model

from cumulusci.core.exceptions import SalesforceException, TaskOptionsError
from cumulusci.core.utils import determine_managed_mode
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils import inject_namespace
from cumulusci.utils.options import CCIOptions, CCIOptionType, Field


class PermissionSetGroupAssignmentsOption(CCIOptionType):
    """Parses a dictionary of Permission Set Group to Permission Sets assignments.

    Supports formats:
    - JSON: {"PermissionSetGroup1": ["PermissionSet1", "PermissionSet2"]}
    - YAML: PermissionSetGroup1: [PermissionSet1, PermissionSet2]
    - Command line: "PermissionSetGroup1:PermissionSet1,PermissionSet2;PermissionSetGroup2:PermissionSet3,PermissionSet4"
    """

    @classmethod
    def validate(cls, v):
        """Validate and convert a value to Dict[str, List[str]]."""
        # Handle dict input (from YAML/JSON)
        if isinstance(v, dict):
            # Normalize: ensure all values are lists
            normalized = {k: v if isinstance(v, list) else [v] for k, v in v.items()}
        # Handle string input
        elif isinstance(v, str):
            # If it's a JSON string, parse it
            if v.startswith("{") or v.startswith("["):
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    normalized = {
                        k: v if isinstance(v, list) else [v] for k, v in parsed.items()
                    }
                else:
                    raise TaskOptionsError(
                        f"Expected dict in JSON string, got {type(parsed)}"
                    )
            else:
                # Handle command line format: PSG1:PS1,PS2;PSG2:PS3,PS4
                normalized = cls.from_str(v)
        else:
            raise TaskOptionsError(
                f"Invalid format for assignments. Expected dict or string in format "
                f"'PSG1:PS1,PS2;PSG2:PS3,PS4' or JSON dict, got: {type(v)}"
            )

        # Validate with Pydantic using the return type annotation
        target_type = signature(cls.from_str).return_annotation
        Dummy = create_model(cls.name or cls.__name__, __root__=(target_type, ...))
        return Dummy.parse_obj(normalized).__root__

    @classmethod
    def from_str(cls, v) -> Dict[str, List[str]]:
        """Parse command line format: PSG1:PS1,PS2;PSG2:PS3,PS4 or PSG1:PS1"""
        # Handle command line format: presence of colon indicates command line format
        if ":" in v:
            result = {}
            # Split by semicolon to get groups (if multiple groups)
            # If no semicolon, treat entire string as single group assignment
            group_assignments = v.split(";") if ";" in v else [v]

            for group_assignment in group_assignments:
                group_assignment = group_assignment.strip()
                if ":" in group_assignment:
                    psg_name, ps_names = group_assignment.split(":", maxsplit=1)
                    psg_name = psg_name.strip()
                    # Split permission sets by comma (if multiple permission sets)
                    # If no comma, treat entire string as single permission set
                    ps_list = [ps.strip() for ps in ps_names.split(",") if ps.strip()]
                    if psg_name:
                        result[psg_name] = ps_list
            return result

        raise TaskOptionsError(
            "Invalid format for assignments. Expected string in format "
            "'PSG1:PS1' or 'PSG1:PS1,PS2;PSG2:PS3,PS4'"
        )


class AssignPermissionSetToPermissionSetGroup(BaseSalesforceApiTask):
    """Assign Permission Sets to Permission Set Groups.

    This task creates PermissionSetGroupComponent records to associate
    Permission Sets with Permission Set Groups using the Composite API.

    Task options:
    - assignments: A dictionary where:
      key: Permission Set Group API name (DeveloperName)
       - value: List of Permission Set API names (Name) to assign to the Permission Set Group

    Example 1: Passed as JSON
    "PermissionSetGroup1": ["PermissionSet1", "PermissionSet2"]
    "PermissionSetGroup2": ["PermissionSet3", "PermissionSet4"]

    Example 2: Passed as YAML
    PermissionSetGroup1:
      - PermissionSet1
      - PermissionSet2
    PermissionSetGroup2:
      - PermissionSet3
      - PermissionSet4

    Example 3: Passed in command line arguments
    - --assignments "PermissionSetGroup1:PermissionSet1,PermissionSet2;PermissionSetGroup2:PermissionSet3,PermissionSet4"
    - --assignments "PermissionSetGroup1:PermissionSet1;"
    """

    class Options(CCIOptions):
        assignments: PermissionSetGroupAssignmentsOption = Field(
            ...,
            description=(
                "Dictionary mapping Permission Set Group API names to lists of "
                "Permission Set API names. Supports JSON, YAML, or command line format."
            ),
        )
        namespace_inject: str = Field(
            None,
            description="Namespace to use for Permission Set names. If not provided, the namespace from the project config will be used.",
        )
        managed: bool = Field(
            None,
            description="Whether the deployment is managed. If not provided, the managed mode will be determined based on the org config.",
        )
        fail_on_error: bool = Field(
            False,
            description="Whether the task should fail if any Permission Set Group Component creation fails.",
        )

    parsed_options: Options

    def _init_options(self, kwargs):
        super()._init_options(kwargs)

        if self.parsed_options.namespace_inject is None:
            self.parsed_options.namespace_inject = (
                self.project_config.project__package__namespace
            )

        if self.parsed_options.managed is None:
            self.parsed_options.managed = determine_managed_mode(
                self.parsed_options, self.project_config, self.org_config
            )

        self.namespaced_org = bool(
            self.parsed_options.namespace_inject
        ) and self.parsed_options.namespace_inject == getattr(
            self.org_config, "namespace", None
        )

        self.psg_names_sanitized = {}
        self.ps_names_sanitized = {}

    def _run_task(self):
        """Execute the task to assign Permission Sets to Permission Set Groups."""
        assignments = self.parsed_options.assignments

        if not assignments:
            self.logger.warning("No assignments provided. Nothing to do.")
            return

        # Step 1: Query Permission Set Groups to get their IDs
        self._get_permission_set_group_ids(list(assignments.keys()))

        # Step 2: Query Permission Sets to get their IDs
        all_ps_names = []
        for ps_list in assignments.values():
            all_ps_names.extend(ps_list)

        self._get_permission_set_ids(all_ps_names)

        # Step 3: Build composite request to create PermissionSetGroupComponent records
        records = []
        for psg_name, ps_names in assignments.items():
            psg_id = self.psg_ids.get(self.psg_names_sanitized[psg_name])
            if not psg_id:
                self.logger.warning(
                    f"Permission Set Group '{psg_name}' not found in the org. Skipping assignment creation."
                )
                continue

            for ps_name in ps_names:
                ps_id = self.ps_ids.get(self.ps_names_sanitized[ps_name])
                if not ps_id:
                    self.logger.warning(
                        f"Permission Set '{ps_name}' not found in the org. Skipping assignment creation."
                    )
                    continue

                records.append(
                    {
                        "attributes": {"type": "PermissionSetGroupComponent"},
                        "PermissionSetGroupId": psg_id,
                        "PermissionSetId": ps_id,
                    }
                )

        if not records:
            self.logger.warning("No valid records to create. Nothing to do.")
            return

        # Step 4: Use Composite API to create records in batches of 200
        for i in range(0, len(records), 200):
            batch = records[i : i + 200]
            self.logger.info(f"Processing batch {i // 200 + 1} ({len(batch)} records)")
            try:
                self._create_permission_set_group_components(batch)
            except Exception as e:
                self.logger.error(f"Error processing batch {i // 200 + 1}: {str(e)}")
                if self.parsed_options.fail_on_error:
                    raise e

    def _get_permission_set_group_ids(self, psg_names: List[str]):
        """Query Permission Set Groups by DeveloperName and return mapping of name to ID."""
        self.psg_ids = {}
        if not psg_names:
            self.logger.warning("No Permission Set Groups provided. Nothing to do.")
            return

        self.psg_names_sanitized = self._process_namespaces(psg_names)

        name_conditions, name_mapping = self._build_name_conditions(
            list(self.psg_names_sanitized.values()), field_name="DeveloperName"
        )

        query = (
            f"SELECT Id, DeveloperName, NamespacePrefix FROM PermissionSetGroup "
            f"WHERE ({' OR '.join(name_conditions)})"
        )

        try:
            result = self.sf.query(query)
            for record in result.get("records", []):
                record_name = record["DeveloperName"]
                namespace_prefix = record.get("NamespacePrefix")
                key = (record_name, namespace_prefix)
                if key in name_mapping:
                    original_name = name_mapping[key]
                    self.psg_ids[original_name] = record["Id"]
                elif (record_name, None) in name_mapping:
                    original_name = name_mapping[(record_name, None)]
                    self.psg_ids[original_name] = record["Id"]

            # Log missing groups
            missing = set(self.psg_names_sanitized.values()) - set(self.psg_ids.keys())
            if missing:
                self.logger.warning(
                    f"Permission Set Groups not found in the org: {', '.join(missing)}"
                )

            return
        except Exception as e:
            raise SalesforceException(
                f"Error querying Permission Set Groups: {str(e)}"
            ) from e

    def _process_namespaces(self, names: List[str]):
        """Process namespace tokens in names."""
        # names_json_string = json.dumps(names)
        names_processed = {}
        for name in names:
            _, name_processed = inject_namespace(
                "",
                name,
                namespace=self.parsed_options.namespace_inject,
                managed=self.parsed_options.managed,
                namespaced_org=self.namespaced_org,
                logger=self.logger,
            )
            names_processed[name] = name_processed
        return names_processed

    def _build_name_conditions(self, names: List[str], field_name: str = "Name"):
        name_conditions = []
        name_mapping = (
            {}
        )  # Maps (original_name, namespace_prefix) tuple back to original name
        for name in names:
            # Check if name contains namespace prefix (format: namespace__Name)
            if "__" in name and self.parsed_options.namespace_inject:
                parts = name.split("__", 1)
                if len(parts) == 2:
                    ns_prefix, ps_name = parts
                    # Query with namespace prefix
                    escaped_ns = "'" + ns_prefix.replace("'", "''") + "'"
                    escaped_name = "'" + ps_name.replace("'", "''") + "'"
                    name_conditions.append(
                        f"(NamespacePrefix = {escaped_ns} AND {field_name} = {escaped_name})"
                    )
                    name_mapping[(ps_name, ns_prefix)] = name
                else:
                    # Fallback: query by name only
                    escaped_name = "'" + name.replace("'", "''") + "'"
                    name_conditions.append(f"{field_name} = {escaped_name}")
                    name_mapping[(name, None)] = name
            else:
                # No namespace prefix in name
                escaped_name = "'" + name.replace("'", "''") + "'"
                name_conditions.append(f"{field_name} = {escaped_name}")
                name_mapping[(name, None)] = name

        return name_conditions, name_mapping

    def _get_permission_set_ids(self, ps_names: List[str]):
        """Query Permission Sets by Name and return mapping of name to ID.

        Handles namespace tokens (%%%NAMESPACE%%%) in Permission Set names by:
        1. Replacing tokens with actual namespace prefix
        2. Querying using both Name and NamespacePrefix fields
        """
        self.ps_ids = {}
        if not ps_names:
            self.logger.warning("No Permission Sets provided. Nothing to do.")
            return

        # Remove duplicates while preserving order
        unique_ps_names = list(dict.fromkeys(ps_names))

        # Process namespace tokens in Permission Set names
        self.ps_names_sanitized = self._process_namespaces(unique_ps_names)

        # Replace namespace tokens in names and build query conditions
        name_conditions, name_mapping = self._build_name_conditions(
            list(self.ps_names_sanitized.values())
        )

        # Build SOQL query with namespace handling
        query = (
            f"SELECT Id, Name, NamespacePrefix FROM PermissionSet "
            f"WHERE IsOwnedByProfile = false AND ({' OR '.join(name_conditions)})"
        )

        try:
            result = self.sf.query(query)

            # Build mapping considering namespace prefix
            for record in result.get("records", []):
                record_name = record["Name"]
                namespace_prefix = record.get("NamespacePrefix")

                # Try to match by (name, namespace_prefix) tuple
                key = (record_name, namespace_prefix)
                if key in name_mapping:
                    original_name = name_mapping[key]
                    self.ps_ids[original_name] = record["Id"]
                # Fallback: match by name only if namespace_prefix is None
                elif (record_name, None) in name_mapping:
                    original_name = name_mapping[(record_name, None)]
                    self.ps_ids[original_name] = record["Id"]

            # Log missing permission sets
            missing = set(self.ps_names_sanitized.values()) - set(self.ps_ids.keys())
            if missing:
                self.logger.warning(
                    f"Permission Sets not found in the org: {', '.join(missing)}"
                )

            return
        except Exception as e:
            raise SalesforceException(
                f"Error querying Permission Sets: {str(e)}"
            ) from e

    def _create_permission_set_group_components(self, records: List[Dict]):
        """Create PermissionSetGroupComponent records using Composite API."""
        request_body = {
            "allOrNone": False,
            "records": records,
        }

        try:
            result = self.sf.restful(
                "composite/sobjects", method="POST", data=json.dumps(request_body)
            )

            # Process response
            composite_response = isinstance(result, list) and result or []
            success_count = 0
            error_count = 0

            for i, response in enumerate(composite_response):
                success = response.get("success", False)
                if success is True:
                    success_count += 1
                    record_id = response.get("id", "Unknown")
                    self.logger.debug(
                        f"Created PermissionSetGroupComponent record: {record_id}"
                    )
                else:

                    errors = response.get("errors", [])
                    is_duplicate_error = any(
                        err.get("statusCode")
                        for err in errors
                        if isinstance(err, dict)
                        and err.get("statusCode", "Unknown status code")
                        == "DUPLICATE_VALUE"
                    )

                    if not is_duplicate_error:
                        error_count += 1

                    error_messages = [
                        f"{err.get('message', 'Unknown error')} ({err.get('statusCode', 'Unknown status code')})"
                        for err in errors
                        if isinstance(err, dict)
                    ]
                    psg_name = next(
                        (
                            key
                            for key, value in self.psg_ids.items()
                            if value
                            == records[i].get("PermissionSetGroupId", "Unknown")
                        ),
                        None,
                    )
                    ps_name = next(
                        (
                            key
                            for key, value in self.ps_ids.items()
                            if value == records[i].get("PermissionSetId", "Unknown")
                        ),
                        None,
                    )

                    if is_duplicate_error:
                        self.logger.info(
                            f"Permission Set '{ps_name}' is already assigned to Permission Set Group '{self.psg_names_sanitized.get(psg_name, psg_name)}'. Skipping assignment creation."
                        )
                    else:
                        self.logger.error(
                            f"Failed to create PermissionSetGroupComponent for Permission Set Group '{self.psg_names_sanitized.get(psg_name, psg_name)}' and Permission Set '{self.ps_names_sanitized.get(ps_name, ps_name)}': {', '.join(error_messages)}"
                        )

            self.logger.info(
                f"Permission Set Group Assignments results: {success_count} succeeded, {error_count} failed"
            )

            if error_count > 0:
                raise SalesforceException(
                    f"Failed to create {error_count} PermissionSetGroupComponent record(s)"
                )

        except Exception as e:
            raise SalesforceException(
                f"Error creating PermissionSetGroupComponent records: {str(e)}"
            ) from e
