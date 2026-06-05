"""Tests for add_public_group_members.py — target coverage > 90%."""

import json
from unittest.mock import Mock

import pytest

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.salesforce.add_public_group_members import (
    AddPublicGroupMembers,
    GroupMemberOption,
)
from cumulusci.tasks.salesforce.tests.util import create_task

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_task(options):
    """Create an AddPublicGroupMembers task with a mocked sf client."""
    task = create_task(AddPublicGroupMembers, options)
    task.sf = Mock()
    return task


# ─────────────────────────────────────────────────────────────────────────────
# GroupMemberOption — validate()
# ─────────────────────────────────────────────────────────────────────────────


class TestGroupMemberOptionValidate:
    def test_valid_dict_input(self):
        data = {"MyGroup": {"roles": ["SomeRole"]}}
        result = GroupMemberOption.validate(data)
        assert "MyGroup" in result
        assert result["MyGroup"]["roles"] == ["SomeRole"]

    def test_valid_json_string_input(self):
        data = json.dumps({"MyGroup": {"users": ["useralias"]}})
        result = GroupMemberOption.validate(data)
        assert result["MyGroup"]["users"] == ["useralias"]

    def test_invalid_json_string_raises_error(self):
        with pytest.raises(TaskOptionsError, match="not valid JSON"):
            GroupMemberOption.validate('{"broken": }')

    def test_non_json_string_raises_error(self):
        with pytest.raises(TaskOptionsError, match="must be a JSON object"):
            GroupMemberOption.validate("just_a_string")

    def test_non_dict_non_string_raises_error(self):
        with pytest.raises(
            TaskOptionsError, match="must be a YAML mapping or a JSON object string"
        ):
            GroupMemberOption.validate(42)

    def test_json_string_with_object_prefix(self):
        """String that starts with '{' and is valid JSON is accepted."""
        raw = '{"G1": {"public_groups": ["OtherGroup"]}}'
        result = GroupMemberOption.validate(raw)
        assert result["G1"]["public_groups"] == ["OtherGroup"]


# ─────────────────────────────────────────────────────────────────────────────
# GroupMemberOption — _parse()
# ─────────────────────────────────────────────────────────────────────────────


class TestGroupMemberOptionParse:
    def test_all_four_member_types_as_lists(self):
        data = {
            "MyGroup": {
                "roles": ["R1", "R2"],
                "roles_subordinates": ["R3"],
                "users": ["u1"],
                "public_groups": ["G2"],
            }
        }
        result = GroupMemberOption._parse(data)
        assert result["MyGroup"]["roles"] == ["R1", "R2"]
        assert result["MyGroup"]["roles_subordinates"] == ["R3"]
        assert result["MyGroup"]["users"] == ["u1"]
        assert result["MyGroup"]["public_groups"] == ["G2"]

    def test_single_string_values_coerced_to_list(self):
        data = {"MyGroup": {"roles": "SingleRole"}}
        result = GroupMemberOption._parse(data)
        assert result["MyGroup"]["roles"] == ["SingleRole"]
        assert result["MyGroup"]["users"] == []

    def test_missing_all_sub_keys_raises_error(self):
        data = {"MyGroup": {}}
        with pytest.raises(TaskOptionsError, match="must have at least one of"):
            GroupMemberOption._parse(data)

    def test_non_dict_group_config_raises_error(self):
        data = {"MyGroup": "not-a-dict"}
        with pytest.raises(TaskOptionsError, match="must be a mapping"):
            GroupMemberOption._parse(data)

    def test_multiple_groups_parsed_correctly(self):
        data = {
            "GroupA": {"roles": ["RoleA"]},
            "GroupB": {"users": ["userB"]},
        }
        result = GroupMemberOption._parse(data)
        assert "GroupA" in result
        assert "GroupB" in result
        assert result["GroupA"]["roles"] == ["RoleA"]
        assert result["GroupB"]["users"] == ["userB"]

    def test_optional_sub_keys_default_to_empty_list(self):
        data = {"MyGroup": {"roles": ["R1"]}}
        result = GroupMemberOption._parse(data)
        assert result["MyGroup"]["roles_subordinates"] == []
        assert result["MyGroup"]["users"] == []
        assert result["MyGroup"]["public_groups"] == []


# ─────────────────────────────────────────────────────────────────────────────
# GroupMemberOption — _coerce_list()
# ─────────────────────────────────────────────────────────────────────────────


class TestGroupMemberOptionCoerceList:
    def test_none_returns_empty_list(self):
        assert GroupMemberOption._coerce_list(None) == []

    def test_string_returns_single_element_list(self):
        assert GroupMemberOption._coerce_list("hello") == ["hello"]

    def test_list_returned_as_list(self):
        assert GroupMemberOption._coerce_list(["a", "b"]) == ["a", "b"]

    def test_tuple_returned_as_list(self):
        assert GroupMemberOption._coerce_list(("x",)) == ["x"]


# ─────────────────────────────────────────────────────────────────────────────
# AddPublicGroupMembers._in_list()
# ─────────────────────────────────────────────────────────────────────────────


class TestInList:
    def test_single_value(self):
        result = AddPublicGroupMembers._in_list(["hello"])
        assert result == "'hello'"

    def test_multiple_values(self):
        result = AddPublicGroupMembers._in_list(["a", "b", "c"])
        assert result == "'a', 'b', 'c'"

    def test_value_with_single_quote_is_escaped(self):
        result = AddPublicGroupMembers._in_list(["O'Brien"])
        assert result == "'O\\'Brien'"


# ─────────────────────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryHelpers:
    def _task(self):
        task = _make_task({"group_members": {"G": {"roles": ["R"]}}})
        return task

    def test_query_public_groups(self):
        task = self._task()
        task.sf.query.return_value = {
            "records": [
                {"DeveloperName": "GroupA", "Id": "0F9A1"},
                {"DeveloperName": "GroupB", "Id": "0F9B2"},
            ]
        }
        result = task._query_public_groups(["GroupA", "GroupB"])
        assert result == {"GroupA": "0F9A1", "GroupB": "0F9B2"}
        called_sql = task.sf.query.call_args[0][0]
        assert "Type = 'Regular'" in called_sql
        assert "'GroupA'" in called_sql

    def test_query_user_roles(self):
        task = self._task()
        task.sf.query.return_value = {
            "records": [{"DeveloperName": "SalesRep", "Id": "00E01"}]
        }
        result = task._query_user_roles(["SalesRep"])
        assert result == {"SalesRep": "00E01"}
        assert "UserRole" in task.sf.query.call_args[0][0]

    def test_query_role_groups(self):
        task = self._task()
        task.sf.query.return_value = {
            "records": [{"RelatedId": "00E01", "Id": "0F9C3"}]
        }
        result = task._query_role_groups(["00E01"], "Role")
        assert result == {"00E01": "0F9C3"}
        called_sql = task.sf.query.call_args[0][0]
        assert "Type = 'Role'" in called_sql

    def test_query_users_by_alias(self):
        task = self._task()
        task.sf.query.return_value = {"records": [{"Alias": "jdoe", "Id": "005U1"}]}
        result = task._query_users_by_alias(["jdoe"])
        assert result == {"jdoe": "005U1"}
        called_sql = task.sf.query.call_args[0][0]
        assert "IsActive = true" in called_sql

    def test_query_existing_members_groups_by_group_id(self):
        task = self._task()
        task.sf.query.return_value = {
            "records": [
                {"GroupId": "GID1", "UserOrGroupId": "UID1"},
                {"GroupId": "GID1", "UserOrGroupId": "UID2"},
                {"GroupId": "GID2", "UserOrGroupId": "UID3"},
            ]
        }
        result = task._query_existing_members(["GID1", "GID2"])
        assert result["GID1"] == {"UID1", "UID2"}
        assert result["GID2"] == {"UID3"}

    def test_query_existing_members_empty(self):
        task = self._task()
        task.sf.query.return_value = {"records": []}
        result = task._query_existing_members(["GID1"])
        assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# _resolve_role_groups()
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveRoleGroups:
    def _task(self):
        return _make_task({"group_members": {"G": {"roles": ["R"]}}})

    def test_empty_list_returns_empty_dict(self):
        task = self._task()
        result = task._resolve_role_groups([], "Role")
        assert result == {}
        task.sf.query.assert_not_called()

    def test_role_not_found_logs_warning_and_skips(self):
        task = self._task()
        task.logger = Mock()
        # _query_user_roles returns nothing (role not in org)
        task._query_user_roles = Mock(return_value={})
        result = task._resolve_role_groups(["MissingRole"], "Role")
        assert result == {}
        task.logger.warning.assert_called_once()
        warning_msg = task.logger.warning.call_args[0][0]
        assert "Role not found" in warning_msg

    def test_all_roles_missing_returns_empty_dict(self):
        task = self._task()
        task.logger = Mock()
        task._query_user_roles = Mock(return_value={})
        result = task._resolve_role_groups(["R1", "R2"], "Role")
        assert result == {}

    def test_role_group_not_found_logs_warning(self):
        task = self._task()
        task.logger = Mock()
        task._query_user_roles = Mock(return_value={"SalesRep": "00E01"})
        # No matching group returned
        task._query_role_groups = Mock(return_value={})
        result = task._resolve_role_groups(["SalesRep"], "Role")
        assert result == {}
        task.logger.warning.assert_called_once()
        warning_msg = task.logger.warning.call_args[0][0]
        assert "No '%s' group found" in warning_msg

    def test_happy_path_returns_mapping(self):
        task = self._task()
        task.logger = Mock()
        task._query_user_roles = Mock(return_value={"SalesRep": "00E01"})
        task._query_role_groups = Mock(return_value={"00E01": "0F9X1"})
        result = task._resolve_role_groups(["SalesRep"], "Role")
        assert result == {"SalesRep": "0F9X1"}

    def test_partial_roles_found(self):
        task = self._task()
        task.logger = Mock()
        task._query_user_roles = Mock(
            return_value={"FoundRole": "00E01"}
            # "MissingRole" not present
        )
        task._query_role_groups = Mock(return_value={"00E01": "0F9X1"})
        result = task._resolve_role_groups(["FoundRole", "MissingRole"], "Role")
        assert result == {"FoundRole": "0F9X1"}
        # Warning for MissingRole
        task.logger.warning.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _bulk_insert()
# ─────────────────────────────────────────────────────────────────────────────


class TestBulkInsert:
    def _task(self):
        return _make_task({"group_members": {"G": {"roles": ["R"]}}})

    def test_empty_list_logs_and_skips(self):
        task = self._task()
        task.logger = Mock()
        task._bulk_insert([])
        task.logger.info.assert_called_once()
        assert "No new" in task.logger.info.call_args[0][0]
        task.sf.bulk.GroupMember.insert.assert_not_called()

    def test_non_empty_list_calls_bulk_insert(self):
        task = self._task()
        task.logger = Mock()
        members = [{"GroupId": "GID1", "UserOrGroupId": "UID1"}]
        task.sf.bulk.GroupMember.insert.return_value = [{"success": True}]
        task._bulk_insert(members)
        task.sf.bulk.GroupMember.insert.assert_called_once_with(members)

    def test_calls_check_bulk_results(self):
        task = self._task()
        task.logger = Mock()
        results = [{"success": True}]
        task.sf.bulk.GroupMember.insert.return_value = results
        task._check_bulk_results = Mock()
        task._bulk_insert([{"GroupId": "G1", "UserOrGroupId": "U1"}])
        task._check_bulk_results.assert_called_once_with(results)


# ─────────────────────────────────────────────────────────────────────────────
# _check_bulk_results()
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckBulkResults:
    def _task(self):
        return _make_task({"group_members": {"G": {"roles": ["R"]}}})

    def test_all_success_does_not_raise(self):
        task = self._task()
        task.logger = Mock()
        results = [{"success": True}, {"success": True}]
        task._check_bulk_results(results)  # should not raise
        task.logger.info.assert_called_once()

    def test_failure_raises_task_options_error(self):
        task = self._task()
        task.logger = Mock()
        results = [
            {
                "success": False,
                "errors": [
                    {"statusCode": "DUPLICATE_VALUE", "message": "Already in group"}
                ],
            },
        ]
        with pytest.raises(TaskOptionsError, match="failed to insert"):
            task._check_bulk_results(results)

    def test_failure_logs_each_error(self):
        task = self._task()
        task.logger = Mock()
        results = [
            {
                "success": False,
                "errors": [
                    {"statusCode": "ERR1", "message": "First error"},
                    {"statusCode": "ERR2", "message": "Second error"},
                ],
            }
        ]
        with pytest.raises(TaskOptionsError):
            task._check_bulk_results(results)
        assert task.logger.error.call_count == 2

    def test_mixed_results_reports_correct_counts(self):
        task = self._task()
        task.logger = Mock()
        results = [
            {"success": True},
            {"success": False, "errors": [{"statusCode": "E", "message": "Bad"}]},
        ]
        with pytest.raises(TaskOptionsError):
            task._check_bulk_results(results)
        # Info message should mention 1 success, 1 failure
        info_call = task.logger.info.call_args
        assert "1" in str(info_call)


# ─────────────────────────────────────────────────────────────────────────────
# _run_group_members() — integration-style tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRunGroupMembers:
    """Tests for the core _run_group_members() orchestration method."""

    def _task_with_mocked_helpers(self, options):
        task = _make_task(options)
        task.logger = Mock()
        return task

    def test_target_group_not_found_raises_error(self):
        task = self._task_with_mocked_helpers(
            {"group_members": {"MissingGroup": {"roles": ["SomeRole"]}}}
        )
        task._query_public_groups = Mock(return_value={})  # group not found
        with pytest.raises(TaskOptionsError, match="Public group"):
            task._run_group_members()

    def test_happy_path_with_roles_only(self):
        options = {"group_members": {"MyGroup": {"roles": ["SalesRep"]}}}
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(return_value={"MyGroup": "GID1"})
        task._resolve_role_groups = Mock(return_value={"SalesRep": "RGID1"})
        task._query_users_by_alias = Mock(return_value={})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        task._bulk_insert.assert_called_once()
        inserted = task._bulk_insert.call_args[0][0]
        assert len(inserted) == 1
        assert inserted[0] == {"GroupId": "GID1", "UserOrGroupId": "RGID1"}

    def test_happy_path_with_users(self):
        options = {"group_members": {"MyGroup": {"users": ["jdoe"]}}}
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(return_value={"MyGroup": "GID1"})
        task._resolve_role_groups = Mock(return_value={})
        task._query_users_by_alias = Mock(return_value={"jdoe": "UID1"})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        assert {"GroupId": "GID1", "UserOrGroupId": "UID1"} in inserted

    def test_happy_path_with_member_public_groups(self):
        options = {"group_members": {"MyGroup": {"public_groups": ["ChildGroup"]}}}
        task = self._task_with_mocked_helpers(options)

        # First call is for target groups, second for member groups
        task._query_public_groups = Mock(
            side_effect=[
                {"MyGroup": "GID1"},  # target groups
                {"ChildGroup": "GID2"},  # member groups
            ]
        )
        task._resolve_role_groups = Mock(return_value={})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        assert {"GroupId": "GID1", "UserOrGroupId": "GID2"} in inserted

    def test_user_alias_not_found_logs_warning_and_skips(self):
        options = {"group_members": {"MyGroup": {"users": ["unknown"]}}}
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(return_value={"MyGroup": "GID1"})
        task._resolve_role_groups = Mock(return_value={})
        task._query_users_by_alias = Mock(return_value={})  # user not found
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        # Warning logged for missing user
        task.logger.warning.assert_called()
        warning_args = task.logger.warning.call_args[0][0]
        assert "User not found" in warning_args

        # Nothing inserted (skipped)
        inserted = task._bulk_insert.call_args[0][0]
        assert inserted == []

    def test_member_public_group_not_found_logs_warning_and_skips(self):
        options = {"group_members": {"MyGroup": {"public_groups": ["MissingChild"]}}}
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(
            side_effect=[
                {"MyGroup": "GID1"},
                {},  # member group not found
            ]
        )
        task._resolve_role_groups = Mock(return_value={})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        task.logger.warning.assert_called()
        warning_args = task.logger.warning.call_args[0][0]
        assert "Public group not found" in warning_args

        inserted = task._bulk_insert.call_args[0][0]
        assert inserted == []

    def test_deduplication_skips_existing_members(self):
        options = {"group_members": {"MyGroup": {"users": ["jdoe"]}}}
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(return_value={"MyGroup": "GID1"})
        task._resolve_role_groups = Mock(return_value={})
        task._query_users_by_alias = Mock(return_value={"jdoe": "UID1"})
        # jdoe is already a member
        task._query_existing_members = Mock(return_value={"GID1": {"UID1"}})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        assert inserted == []  # nothing new to insert

    def test_deduplication_within_same_run(self):
        """The same member_id should only be inserted once even if listed twice."""
        options = {
            "group_members": {
                "MyGroup": {
                    "roles": ["RoleA"],
                    "public_groups": ["ChildGroup"],
                }
            }
        }
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(
            side_effect=[
                {"MyGroup": "GID1"},
                {"ChildGroup": "SAME_ID"},
            ]
        )
        # Both role and public_group resolve to the same ID
        task._resolve_role_groups = Mock(return_value={"RoleA": "SAME_ID"})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        # Should only appear once
        assert len([r for r in inserted if r["UserOrGroupId"] == "SAME_ID"]) == 1

    def test_all_member_types_combined(self):
        options = {
            "group_members": {
                "MyGroup": {
                    "roles": ["R1"],
                    "roles_subordinates": ["RS1"],
                    "users": ["u1"],
                    "public_groups": ["PG1"],
                }
            }
        }
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(
            side_effect=[
                {"MyGroup": "GID1"},
                {"PG1": "PGID1"},
            ]
        )
        task._resolve_role_groups = Mock(
            side_effect=[
                {"R1": "RGID1"},  # roles
                {"RS1": "RSID1"},  # roles_subordinates
            ]
        )
        task._query_users_by_alias = Mock(return_value={"u1": "UID1"})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        inserted_user_or_group_ids = {r["UserOrGroupId"] for r in inserted}
        assert inserted_user_or_group_ids == {"RGID1", "RSID1", "UID1", "PGID1"}
        assert all(r["GroupId"] == "GID1" for r in inserted)

    def test_multiple_groups_processed(self):
        options = {
            "group_members": {
                "GroupA": {"roles": ["R1"]},
                "GroupB": {"users": ["u2"]},
            }
        }
        task = self._task_with_mocked_helpers(options)

        task._query_public_groups = Mock(
            return_value={"GroupA": "GA_ID", "GroupB": "GB_ID"}
        )
        task._resolve_role_groups = Mock(return_value={"R1": "R1_GID"})
        task._query_users_by_alias = Mock(return_value={"u2": "U2_ID"})
        task._query_existing_members = Mock(return_value={})
        task._bulk_insert = Mock()

        task._run_group_members()

        inserted = task._bulk_insert.call_args[0][0]
        assert len(inserted) == 2
        group_a_records = [r for r in inserted if r["GroupId"] == "GA_ID"]
        group_b_records = [r for r in inserted if r["GroupId"] == "GB_ID"]
        assert len(group_a_records) == 1
        assert group_a_records[0]["UserOrGroupId"] == "R1_GID"
        assert len(group_b_records) == 1
        assert group_b_records[0]["UserOrGroupId"] == "U2_ID"


# ─────────────────────────────────────────────────────────────────────────────
# _run_task()
# ─────────────────────────────────────────────────────────────────────────────


class TestRunTask:
    def test_run_task_calls_run_group_members(self):
        task = _make_task({"group_members": {"G": {"roles": ["R"]}}})
        task._run_group_members = Mock()
        task._run_task()
        task._run_group_members.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end smoke test with fully mocked sf client
# ─────────────────────────────────────────────────────────────────────────────


class TestEndToEnd:
    """Smoke test that wires through _run_task → _run_group_members with sf mocks."""

    def test_full_run_with_roles(self):
        task = _make_task({"group_members": {"CustomerGroup": {"roles": ["SalesRep"]}}})
        task.logger = Mock()

        # Configure sf.query to return appropriate records per query
        def mock_query(soql):
            if "Type = 'Regular'" in soql:
                return {"records": [{"DeveloperName": "CustomerGroup", "Id": "GID1"}]}
            if "UserRole" in soql:
                return {"records": [{"DeveloperName": "SalesRep", "Id": "ROLE1"}]}
            if "Type = 'Role'" in soql:
                return {"records": [{"RelatedId": "ROLE1", "Id": "RGRP1"}]}
            if "GroupMember" in soql:
                return {"records": []}
            return {"records": []}

        task.sf.query.side_effect = mock_query
        task.sf.bulk.GroupMember.insert.return_value = [{"success": True}]

        task._run_task()

        task.sf.bulk.GroupMember.insert.assert_called_once()
        inserted = task.sf.bulk.GroupMember.insert.call_args[0][0]
        assert inserted == [{"GroupId": "GID1", "UserOrGroupId": "RGRP1"}]

    def test_full_run_no_new_members(self):
        task = _make_task({"group_members": {"CustomerGroup": {"users": ["jdoe"]}}})
        task.logger = Mock()

        def mock_query(soql):
            if "Type = 'Regular'" in soql:
                return {"records": [{"DeveloperName": "CustomerGroup", "Id": "GID1"}]}
            if "IsActive = true" in soql:
                return {"records": [{"Alias": "jdoe", "Id": "UID1"}]}
            if "GroupMember" in soql:
                # jdoe already a member
                return {"records": [{"GroupId": "GID1", "UserOrGroupId": "UID1"}]}
            return {"records": []}

        task.sf.query.side_effect = mock_query

        task._run_task()

        # No insert call since already a member
        task.sf.bulk.GroupMember.insert.assert_not_called()

    def test_full_run_bulk_failure_raises(self):
        task = _make_task({"group_members": {"G": {"users": ["jdoe"]}}})
        task.logger = Mock()

        def mock_query(soql):
            if "Type = 'Regular'" in soql:
                return {"records": [{"DeveloperName": "G", "Id": "GID1"}]}
            if "IsActive = true" in soql:
                return {"records": [{"Alias": "jdoe", "Id": "UID1"}]}
            if "GroupMember" in soql:
                return {"records": []}
            return {"records": []}

        task.sf.query.side_effect = mock_query
        task.sf.bulk.GroupMember.insert.return_value = [
            {
                "success": False,
                "errors": [
                    {"statusCode": "DUPLICATE_VALUE", "message": "Already exists"}
                ],
            }
        ]

        with pytest.raises(TaskOptionsError, match="failed to insert"):
            task._run_task()
