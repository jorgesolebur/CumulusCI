"""Add members to Salesforce public groups.

Accepts a ``group_members`` YAML mapping (or JSON object string from the CLI)
that supports four member types per group: roles, roles_subordinates, users
(by alias), and nested public groups.

All resolution and DML is done via SOQL + Bulk API.
"""

import json
from typing import Dict, List, Set

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, CCIOptionType, Field

# ------------------------------------------------------------------ #
# Option type                                                        #
# ------------------------------------------------------------------ #


class GroupMemberOption(CCIOptionType):
    """Parse rich group-membership config from a YAML mapping or CLI JSON string.

    YAML structure
    --------------
    group_members:
      <PublicGroupDevName>:
        roles:              <role devname or list of role devnames>
        roles_subordinates: <role devname or list of role devnames>
        users:              <user alias or list of user aliases>
        public_groups:      <group devname or list of group devnames>

    CLI usage (JSON string)
    -----------------------
    --group_members '{"GroupName": {"roles": ["RoleName"]}}'

    All four sub-keys are optional per group, but at least one must be present.
    """

    name = "GroupMember"

    @classmethod
    def validate(cls, v):
        if isinstance(v, str):
            if v.strip().startswith("{"):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError as exc:
                    raise TaskOptionsError(
                        f"'group_members' string input is not valid JSON: {exc}"
                    ) from exc
            else:
                raise TaskOptionsError(
                    "'group_members' string input must be a JSON object. "
                    'Example: \'{"GroupName": {"roles": ["RoleName"]}}\''
                )
        if not isinstance(v, dict):
            raise TaskOptionsError(
                "'group_members' must be a YAML mapping or a JSON object string."
            )
        return cls._parse(v)

    @classmethod
    def _parse(cls, data: dict) -> Dict[str, Dict[str, List[str]]]:
        result: Dict[str, Dict[str, List[str]]] = {}
        for group_name, cfg in data.items():
            if not isinstance(cfg, dict):
                raise TaskOptionsError(
                    f"group_members['{group_name}'] must be a mapping."
                )
            parsed_cfg = {
                "roles": cls._coerce_list(cfg.get("roles")),
                "roles_subordinates": cls._coerce_list(cfg.get("roles_subordinates")),
                "users": cls._coerce_list(cfg.get("users")),
                "public_groups": cls._coerce_list(cfg.get("public_groups")),
            }
            if not any(parsed_cfg.values()):
                raise TaskOptionsError(
                    f"group_members['{group_name}'] must have at least one of: "
                    "roles, roles_subordinates, users, public_groups."
                )
            result[group_name] = parsed_cfg
        return result

    @staticmethod
    def _coerce_list(value) -> List[str]:
        if value is None:
            return []
        return [value] if isinstance(value, str) else list(value)


# ------------------------------------------------------------------ #
# Task                                                                 #
# ------------------------------------------------------------------ #


class AddPublicGroupMembers(BaseSalesforceApiTask):
    """Add members to Salesforce public groups via SOQL + Bulk API.

    Supports four member types per group: roles, roles_subordinates,
    users (by alias), and nested public groups.
    """

    class Options(CCIOptions):
        group_members: GroupMemberOption = Field(
            ...,
            description=(
                "Mapping of public-group DeveloperName to member config. "
                "Supports roles, roles_subordinates, users (by alias), and public_groups. "
                "Provide as a YAML mapping or a JSON object string from the CLI. "
                "Example (CLI): "
                '{"CustomerBusinessPersona": {"roles": ["ContactCentreOperator"]}}'
            ),
        )

    parsed_options: Options

    # ------------------------------------------------------------------ #
    # Entry point                                                          #
    # ------------------------------------------------------------------ #

    def _run_task(self):
        self._run_group_members()

    # ------------------------------------------------------------------ #
    # Core execution                                                       #
    # ------------------------------------------------------------------ #

    def _run_group_members(self):
        group_members = self.parsed_options.group_members
        target_group_dev_names = list(group_members.keys())

        self.logger.info(
            "Processing %s public group(s).",
            len(target_group_dev_names),
        )

        # Step 1 — Resolve target public groups
        public_group_id_by_dev_name = self._query_public_groups(target_group_dev_names)
        missing = [
            n for n in target_group_dev_names if n not in public_group_id_by_dev_name
        ]
        if missing:
            raise TaskOptionsError(f"Public group(s) not found: {', '.join(missing)}")

        # Collect all distinct values to query
        all_roles = sorted({r for cfg in group_members.values() for r in cfg["roles"]})
        all_roles_sub = sorted(
            {r for cfg in group_members.values() for r in cfg["roles_subordinates"]}
        )
        all_user_aliases = sorted(
            {u for cfg in group_members.values() for u in cfg["users"]}
        )
        all_member_group_names = sorted(
            {g for cfg in group_members.values() for g in cfg["public_groups"]}
        )

        # Step 2 — Resolve roles → Role-type group IDs
        role_group_id_by_dev_name = self._resolve_role_groups(all_roles, "Role")

        # Step 3 — Resolve roles_subordinates → RoleAndSubordinates-type group IDs
        role_sub_group_id_by_dev_name = self._resolve_role_groups(
            all_roles_sub, "RoleAndSubordinates"
        )

        # Step 4 — Resolve users by alias → User IDs
        user_id_by_alias: Dict[str, str] = {}
        if all_user_aliases:
            user_id_by_alias = self._query_users_by_alias(all_user_aliases)
            for alias in all_user_aliases:
                if alias not in user_id_by_alias:
                    self.logger.warning(
                        "User not found for Alias: %s — skipping.", alias
                    )

        # Step 5 — Resolve member public groups → Group IDs
        member_group_id_by_dev_name: Dict[str, str] = {}
        if all_member_group_names:
            member_group_id_by_dev_name = self._query_public_groups(
                all_member_group_names
            )
            for dev_name in all_member_group_names:
                if dev_name not in member_group_id_by_dev_name:
                    self.logger.warning(
                        "Public group not found for DeveloperName: %s — skipping.",
                        dev_name,
                    )

        # Step 6 — Fetch existing GroupMember records (deduplication)
        public_group_ids = list(public_group_id_by_dev_name.values())
        existing_by_group_id = self._query_existing_members(public_group_ids)

        # Step 7 — Build and insert
        members_to_insert: List[Dict[str, str]] = []
        for group_dev_name, cfg in group_members.items():
            group_id = public_group_id_by_dev_name[group_dev_name]
            existing = existing_by_group_id.get(group_id, set())

            candidates = (
                [role_group_id_by_dev_name.get(r) for r in cfg["roles"]]
                + [
                    role_sub_group_id_by_dev_name.get(r)
                    for r in cfg["roles_subordinates"]
                ]
                + [user_id_by_alias.get(u) for u in cfg["users"]]
                + [member_group_id_by_dev_name.get(g) for g in cfg["public_groups"]]
            )
            for member_id in candidates:
                if member_id and member_id not in existing:
                    members_to_insert.append(
                        {"GroupId": group_id, "UserOrGroupId": member_id}
                    )
                    existing.add(member_id)

        self._bulk_insert(members_to_insert)

    def _resolve_role_groups(
        self, role_dev_names: List[str], group_type: str
    ) -> Dict[str, str]:
        """Return {roleDeveloperName: roleGroupId} for the given group_type.

        Warns and skips roles whose UserRole or corresponding Group record
        cannot be found.
        """
        if not role_dev_names:
            return {}

        role_id_by_dev_name = self._query_user_roles(role_dev_names)
        for dev_name in role_dev_names:
            if dev_name not in role_id_by_dev_name:
                self.logger.warning(
                    "Role not found for DeveloperName: %s — skipping.", dev_name
                )

        if not role_id_by_dev_name:
            return {}

        role_group_id_by_role_id = self._query_role_groups(
            list(role_id_by_dev_name.values()), group_type
        )

        result: Dict[str, str] = {}
        for dev_name, role_id in role_id_by_dev_name.items():
            if role_id in role_group_id_by_role_id:
                result[dev_name] = role_group_id_by_role_id[role_id]
            else:
                self.logger.warning(
                    "No '%s' group found for role '%s' — skipping.",
                    group_type,
                    dev_name,
                )
        return result

    # ------------------------------------------------------------------ #
    # Query helpers                                                        #
    # ------------------------------------------------------------------ #

    def _query_public_groups(self, dev_names: List[str]) -> Dict[str, str]:
        """Return {DeveloperName: Id} for Regular groups matching dev_names."""
        records = self.sf.query(
            "SELECT Id, DeveloperName FROM Group "
            f"WHERE Type = 'Regular' AND DeveloperName IN ({self._in_list(dev_names)})"
        ).get("records", [])
        return {r["DeveloperName"]: r["Id"] for r in records}

    def _query_user_roles(self, dev_names: List[str]) -> Dict[str, str]:
        """Return {DeveloperName: Id} for UserRole records matching dev_names."""
        records = self.sf.query(
            "SELECT Id, DeveloperName FROM UserRole "
            f"WHERE DeveloperName IN ({self._in_list(dev_names)})"
        ).get("records", [])
        return {r["DeveloperName"]: r["Id"] for r in records}

    def _query_role_groups(
        self, role_ids: List[str], group_type: str
    ) -> Dict[str, str]:
        """Return {RelatedId: Id} for Group records of group_type linked to role_ids."""
        records = self.sf.query(
            "SELECT Id, RelatedId FROM Group "
            f"WHERE Type = '{group_type}' AND RelatedId IN ({self._in_list(role_ids)})"
        ).get("records", [])
        return {r["RelatedId"]: r["Id"] for r in records}

    def _query_users_by_alias(self, aliases: List[str]) -> Dict[str, str]:
        """Return {Alias: Id} for active User records matching aliases."""
        records = self.sf.query(
            "SELECT Id, Alias FROM User "
            f"WHERE IsActive = true AND Alias IN ({self._in_list(aliases)})"
        ).get("records", [])
        return {r["Alias"]: r["Id"] for r in records}

    def _query_existing_members(self, group_ids: List[str]) -> Dict[str, Set[str]]:
        """Return {GroupId: set(UserOrGroupId)} for existing GroupMember records."""
        records = self.sf.query(
            "SELECT GroupId, UserOrGroupId FROM GroupMember "
            f"WHERE GroupId IN ({self._in_list(group_ids)})"
        ).get("records", [])
        result: Dict[str, Set[str]] = {}
        for rec in records:
            result.setdefault(rec["GroupId"], set()).add(rec["UserOrGroupId"])
        return result

    # ------------------------------------------------------------------ #
    # Bulk insert + result check                                           #
    # ------------------------------------------------------------------ #

    def _bulk_insert(self, members_to_insert: List[Dict[str, str]]) -> None:
        if not members_to_insert:
            self.logger.info("No new GroupMember records to insert.")
            return
        self.logger.info(
            "Inserting %s new GroupMember record(s).", len(members_to_insert)
        )
        results = self.sf.bulk.GroupMember.insert(members_to_insert)
        self._check_bulk_results(results)

    def _check_bulk_results(self, results) -> None:
        """Log per-record outcomes; raise TaskOptionsError if any record failed."""
        failures = [r for r in results if not r.get("success")]
        successes = len(results) - len(failures)
        self.logger.info(
            "GroupMember insert: %s succeeded, %s failed.", successes, len(failures)
        )
        if failures:
            for f in failures:
                for err in f.get("errors", []):
                    self.logger.error(
                        "Insert failed: [%s] %s",
                        err.get("statusCode"),
                        err.get("message"),
                    )
            raise TaskOptionsError(
                f"{len(failures)} GroupMember record(s) failed to insert. "
                "See errors above."
            )

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _in_list(values: List[str]) -> str:
        """Format a list of strings as a SOQL IN clause value list."""
        escaped = [v.replace("'", "\\'") for v in values]
        return ", ".join(f"'{v}'" for v in escaped)
