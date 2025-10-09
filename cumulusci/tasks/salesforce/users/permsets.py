import json

from cumulusci.cli.ui import CliTable
from cumulusci.core.exceptions import CumulusCIException
from cumulusci.core.utils import determine_managed_mode, process_list_arg
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils import inject_namespace


class AssignPermissionSets(BaseSalesforceApiTask):
    task_docs = """
Assigns Permission Sets whose Names are in ``api_names`` to either the default org user or the user whose Alias is ``user_alias``. This task skips assigning Permission Sets that are already assigned.

Permission Set names can include namespace tokens that will be replaced based on the context:
- ``%%%NAMESPACE%%%`` is replaced with the package's namespace in managed contexts (e.g., when the package is installed)
- ``%%%NAMESPACED_ORG%%%`` is replaced with the package's namespace in namespaced orgs only (e.g., packaging orgs)
- ``%%%NAMESPACE_OR_C%%%`` is replaced with the namespace in managed contexts, or 'c' otherwise
- ``%%%NAMESPACED_ORG_OR_C%%%`` is replaced with the namespace in namespaced orgs, or 'c' otherwise

The managed mode and namespaced org detection is automatic based on the org context.
    """

    task_options = {
        "api_names": {
            "description": "API Names of desired Permission Sets, separated by commas. Can include namespace tokens like %%%NAMESPACE%%%.",
            "required": True,
        },
        "user_alias": {
            "description": "Target user aliases, separated by commas. Defaults to the current running user."
        },
    }

    permission_name = "PermissionSet"
    permission_name_field = "Name"
    permission_label = "Permission Set"
    assignment_name = "PermissionSetAssignment"
    assignment_lookup = "PermissionSetId"
    assignment_child_relationship = "PermissionSetAssignments"

    def _init_options(self, kwargs):
        super()._init_options(kwargs)

        self.options["api_names"] = process_list_arg(self.options["api_names"])
        self.options["user_alias"] = process_list_arg(
            self.options.get("user_alias") or []
        )

    def _init_namespace_injection(self):
        """Initialize namespace injection options for processing permission set names.

        This automatically determines managed mode and namespaced org context based on:
        - Whether the package is installed in the org (managed mode)
        - Whether we're in a packaging org (namespaced org)
        """
        namespace = self.project_config.project__package__namespace

        # Automatically determine managed mode based on org context
        managed = determine_managed_mode(
            self.options, self.project_config, self.org_config
        )

        # Automatically determine if we're in a namespaced org (e.g., packaging org)
        namespaced_org = bool(namespace) and namespace == getattr(
            self.org_config, "namespace", None
        )

        # Store in options for use by inject_namespace
        self.options["namespace_inject"] = namespace
        self.options["managed"] = managed
        self.options["namespaced_org"] = namespaced_org

    def _inject_namespace(self, text):
        """Inject the namespace into the given text if running in managed mode."""
        if self.org_config is None:
            return text
        return inject_namespace(
            "",
            text,
            namespace=self.options.get("namespace_inject"),
            managed=self.options.get("managed") or False,
            namespaced_org=self.options.get("namespaced_org"),
        )[1]

    def _run_task(self):
        # Initialize namespace injection only if tokens are present or options are set
        if self.org_config and self._needs_namespace_injection():
            self._init_namespace_injection()
            # Process namespace tokens in api_names
            self.options["api_names"] = [
                self._inject_namespace(api_name)
                for api_name in self.options["api_names"]
            ]

        users = self._query_existing_assignments()
        users_assigned_perms = {
            user["Id"]: self._get_assigned_perms(user) for user in users
        }
        perms_by_id = self._get_perm_ids()

        records_to_insert = []
        for user_id, assigned_perms in users_assigned_perms.items():
            records_to_insert.extend(
                self._get_assignments(user_id, assigned_perms, perms_by_id)
            )

        self._insert_assignments(records_to_insert)

    def _needs_namespace_injection(self):
        """Check if namespace injection is needed based on presence of tokens in api_names."""
        namespace_tokens = [
            "%%%NAMESPACE%%%",
            "%%%NAMESPACED_ORG%%%",
            "%%%NAMESPACE_OR_C%%%",
            "%%%NAMESPACED_ORG_OR_C%%%",
            "%%%NAMESPACE_DOT%%%",
        ]
        return any(
            any(token in api_name for token in namespace_tokens)
            for api_name in self.options["api_names"]
        )

    def _query_existing_assignments(self):
        if not self.options["user_alias"]:
            query = (
                f"SELECT Id,(SELECT {self.assignment_lookup} FROM {self.assignment_child_relationship}) "
                "FROM User "
                f"WHERE Username = '{self.org_config.username}'"
            )
        else:
            aliases = "','".join(self.options["user_alias"])
            query = (
                f"SELECT Id,(SELECT {self.assignment_lookup} FROM {self.assignment_child_relationship}) "
                "FROM User "
                f"""WHERE Alias IN ('{aliases}')"""
            )

        result = self.sf.query(query)
        if result["totalSize"] == 0:
            raise CumulusCIException(
                "No Users were found matching the specified aliases."
            )
        return result["records"]

    def _get_assigned_perms(self, user):
        assigned_perms = {}
        # PermissionSetLicenseAssignments actually returns None if there are no assignments instead of an empty list of records.  Wow.
        if user[self.assignment_child_relationship]:
            assigned_perms = {
                r[self.assignment_lookup]
                for r in user[self.assignment_child_relationship]["records"]
            }
        return assigned_perms

    def _get_perm_ids(self):
        api_names = "', '".join(self.options["api_names"])
        perms = self.sf.query(
            f"SELECT Id,{self.permission_name_field} FROM {self.permission_name} WHERE {self.permission_name_field} IN ('{api_names}')"
        )
        perms_by_ids = {
            p["Id"]: p[self.permission_name_field] for p in perms["records"]
        }

        missing_perms = [
            api_name
            for api_name in self.options["api_names"]
            if api_name not in perms_by_ids.values()
        ]
        if missing_perms:
            raise CumulusCIException(
                f"The following {self.permission_label}s were not found: {', '.join(missing_perms)}."
            )
        return perms_by_ids

    def _get_assignments(self, user_id, assigned_perms, perms_by_id):
        assignments = []
        for perm, perm_name in perms_by_id.items():
            if perm not in assigned_perms:
                self.logger.info(
                    f'Assigning {self.permission_label} "{perm_name}" to {user_id}.'
                )
                assignment = {
                    "attributes": {"type": self.assignment_name},
                    "AssigneeId": user_id,
                    self.assignment_lookup: perm,
                }
                assignments.append(assignment)
            else:
                self.logger.warning(
                    f'{self.permission_label} "{perm_name}" is already assigned to {user_id}.'
                )
        return assignments

    def _insert_assignments(self, records_to_insert):
        result_list = []
        for i in range(0, len(records_to_insert), 200):
            request_body = json.dumps(
                {"allOrNone": False, "records": records_to_insert[i : i + 200]}
            )
            result = self.sf.restful(
                "composite/sobjects", method="POST", data=request_body
            )
            result_list.extend(result)
        self._process_composite_results(result_list)

    def _process_composite_results(self, api_results):
        results_table_data = [["Success", "ID", "Message"]]
        for result in api_results:
            result_row = [result["success"], result.get("id", "-")]
            if not result["success"] and result["errors"]:
                result_row.append(result["errors"][0]["message"])
            else:
                result_row.append("-")
            results_table_data.append(result_row)

        table = CliTable(
            results_table_data,
            title="Results",
        )
        table.echo()

        if not all([result["success"] for result in api_results]):
            raise CumulusCIException(
                f"Not all {self.assignment_child_relationship} were saved."
            )


class AssignPermissionSetLicenses(AssignPermissionSets):
    task_docs = """
Assigns Permission Set Licenses whose Developer Names or PermissionSetLicenseKey are in ``api_names`` to either the default org user or the user whose Alias is ``user_alias``. This task skips assigning Permission Set Licenses that are already assigned.

Permission Set Licenses are usually associated with a Permission Set, and assigning the Permission Set usually assigns the associated Permission Set License automatically.  However, in non-namespaced developer scratch orgs, assigning the associated Permission Set may not automatically assign the Permission Set License, and this task will ensure the Permission Set Licenses are assigned.
    """

    task_options = {
        "api_names": {
            "description": "API Developer Names of desired Permission Set Licenses, separated by commas.",
            "required": True,
        },
        "user_alias": {
            "description": "Alias of target user (if not the current running user, the default)."
        },
    }

    permission_name = "PermissionSetLicense"
    permission_name_field = ["DeveloperName", "PermissionSetLicenseKey"]
    permission_label = "Permission Set License"
    assignment_name = "PermissionSetLicenseAssign"
    assignment_lookup = "PermissionSetLicenseId"
    assignment_child_relationship = "PermissionSetLicenseAssignments"

    def _get_perm_ids(self):
        perms_by_ids = {}
        api_names = "', '".join(self.options["api_names"])
        perms = self.sf.query(
            f"SELECT Id,{self.permission_name_field[0]},{self.permission_name_field[1]} FROM {self.permission_name} WHERE {self.permission_name_field[0]} IN ('{api_names}') OR {self.permission_name_field[1]} IN ('{api_names}')"
        )
        for p in perms["records"]:
            if p[self.permission_name_field[0]] in self.options["api_names"]:
                perms_by_ids[p["Id"]] = p[self.permission_name_field[0]]
            else:
                perms_by_ids[p["Id"]] = p[self.permission_name_field[1]]

        missing_perms = [
            api_name
            for api_name in self.options["api_names"]
            if api_name not in perms_by_ids.values()
        ]
        if missing_perms:
            raise CumulusCIException(
                f"The following {self.permission_label}s were not found: {', '.join(missing_perms)}."
            )
        return perms_by_ids


class AssignPermissionSetGroups(AssignPermissionSets):
    task_docs = """
Assigns Permission Set Groups whose Developer Names are in ``api_names`` to either the default org user or the user whose Alias is ``user_alias``. This task skips assigning Permission Set Groups that are already assigned.
    """

    task_options = {
        "api_names": {
            "description": "API Developer Names of desired Permission Set Groups, separated by commas.",
            "required": True,
        },
        "user_alias": {
            "description": "Alias of target user (if not the current running user, the default)."
        },
    }

    permission_name = "PermissionSetGroup"
    permission_name_field = "DeveloperName"
    permission_label = "Permission Set Group"
    assignment_name = "PermissionSetAssignment"
    assignment_lookup = "PermissionSetGroupId"
    assignment_child_relationship = "PermissionSetAssignments"
