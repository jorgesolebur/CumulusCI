import json
from unittest import mock

import pytest
import responses

from cumulusci.core.exceptions import SalesforceException, TaskOptionsError
from cumulusci.tasks.salesforce.assign_ps_psg import (
    AssignPermissionSetToPermissionSetGroup,
    PermissionSetGroupAssignmentsOption,
)
from cumulusci.tests.util import CURRENT_SF_API_VERSION

from .util import create_task


class TestPermissionSetGroupAssignmentsOption:
    """Test PermissionSetGroupAssignmentsOption validation"""

    def test_validate_dict_input(self):
        """Test validation with dict input"""
        assignments = {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3"]}
        result = PermissionSetGroupAssignmentsOption.validate(assignments)
        assert result == {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3"]}

    def test_validate_dict_with_single_value(self):
        """Test validation with dict where value is a single string"""
        assignments = {"PSG1": "PS1", "PSG2": ["PS2", "PS3"]}
        result = PermissionSetGroupAssignmentsOption.validate(assignments)
        assert result == {"PSG1": ["PS1"], "PSG2": ["PS2", "PS3"]}

    def test_validate_json_string(self):
        """Test validation with JSON string"""
        json_str = '{"PSG1": ["PS1", "PS2"], "PSG2": ["PS3"]}'
        result = PermissionSetGroupAssignmentsOption.validate(json_str)
        assert result == {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3"]}

    def test_validate_json_string_with_single_value(self):
        """Test validation with JSON string where value is a single string"""
        json_str = '{"PSG1": "PS1", "PSG2": ["PS2"]}'
        result = PermissionSetGroupAssignmentsOption.validate(json_str)
        assert result == {"PSG1": ["PS1"], "PSG2": ["PS2"]}

    def test_validate_command_line_format(self):
        """Test validation with command line format"""
        cmd_str = "PSG1:PS1,PS2;PSG2:PS3,PS4"
        result = PermissionSetGroupAssignmentsOption.validate(cmd_str)
        assert result == {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3", "PS4"]}

    def test_validate_command_line_format_with_spaces(self):
        """Test validation with command line format with spaces"""
        cmd_str = "PSG1: PS1 , PS2 ; PSG2: PS3 , PS4"
        result = PermissionSetGroupAssignmentsOption.validate(cmd_str)
        assert result == {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3", "PS4"]}

    def test_validate_invalid_type(self):
        """Test validation with invalid type"""
        with pytest.raises(TaskOptionsError, match="Invalid format"):
            PermissionSetGroupAssignmentsOption.validate(123)

    def test_validate_invalid_json_string(self):
        """Test validation with invalid JSON string"""
        import json

        with pytest.raises((TaskOptionsError, json.JSONDecodeError)):
            PermissionSetGroupAssignmentsOption.validate('{"invalid": json}')

    def test_validate_json_array_instead_of_dict(self):
        """Test validation with JSON array instead of dict"""
        with pytest.raises(TaskOptionsError, match="Expected dict"):
            PermissionSetGroupAssignmentsOption.validate('["PSG1", "PSG2"]')

    def test_from_str_valid_format(self):
        """Test from_str with valid format"""
        cmd_str = "PSG1:PS1,PS2;PSG2:PS3"
        result = PermissionSetGroupAssignmentsOption.from_str(cmd_str)
        assert result == {"PSG1": ["PS1", "PS2"], "PSG2": ["PS3"]}

    def test_from_str_invalid_format(self):
        """Test from_str with invalid format"""
        with pytest.raises(TaskOptionsError, match="Invalid format"):
            PermissionSetGroupAssignmentsOption.from_str("invalid")

    def test_from_str_empty_string(self):
        """Test from_str with empty string"""
        with pytest.raises(TaskOptionsError, match="Invalid format"):
            PermissionSetGroupAssignmentsOption.from_str("")


class TestAssignPermissionSetToPermissionSetGroup:
    """Test AssignPermissionSetToPermissionSetGroup task"""

    def test_init_options_with_namespace(self):
        """Test _init_options with namespace provided"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {
                "assignments": {"PSG1": ["PS1"]},
                "namespace_inject": "test_namespace",
            },
        )
        assert task.parsed_options.namespace_inject == "test_namespace"

    def test_init_options_without_namespace(self):
        """Test _init_options without namespace (uses project config)"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task.project_config.project__package__namespace = "project_namespace"
        task._init_options({})
        assert task.parsed_options.namespace_inject == "project_namespace"

    def test_init_options_with_managed(self):
        """Test _init_options with managed flag"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {
                "assignments": {"PSG1": ["PS1"]},
                "managed": True,
            },
        )
        assert task.parsed_options.managed is True

    def test_init_options_without_managed(self):
        """Test _init_options without managed flag (determines from config)"""
        with mock.patch(
            "cumulusci.tasks.salesforce.assign_ps_psg.determine_managed_mode",
            return_value=False,
        ):
            task = create_task(
                AssignPermissionSetToPermissionSetGroup,
                {"assignments": {"PSG1": ["PS1"]}},
            )
            task._init_options({})
            assert task.parsed_options.managed is False

    def test_init_options_namespaced_org(self):
        """Test _init_options sets namespaced_org correctly"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {
                "assignments": {"PSG1": ["PS1"]},
                "namespace_inject": "test_namespace",
            },
        )
        task.org_config.namespace = "test_namespace"
        task._init_options({})
        assert task.namespaced_org is True

    def test_init_options_non_namespaced_org(self):
        """Test _init_options sets namespaced_org to False when namespaces don't match"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {
                "assignments": {"PSG1": ["PS1"]},
                "namespace_inject": "test_namespace",
            },
        )
        task.org_config.namespace = "different_namespace"
        task._init_options({})
        assert task.namespaced_org is False

    @responses.activate
    def test_run_task_empty_assignments(self):
        """Test _run_task with empty assignments"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {}},
        )
        task._run_task()
        # Should not raise and should not make any API calls
        assert len(responses.calls) == 0

    @responses.activate
    def test_run_task_success(self):
        """Test _run_task with successful assignment"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1", "PS2"]}},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+DeveloperName%2C+NamespacePrefix+FROM+PermissionSetGroup+WHERE+%28DeveloperName+%3D+%27PSG1%27%29",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+Name%2C+NamespacePrefix+FROM+PermissionSet+WHERE+IsOwnedByProfile+%3D+false+AND+%28Name+%3D+%27PS1%27+OR+Name+%3D+%27PS2%27%29",
            status=200,
            json={
                "totalSize": 2,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None},
                    {"Id": "0PS000000000002", "Name": "PS2", "NamespacePrefix": None},
                ],
            },
        )

        # Mock Composite API
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {"id": "0PGC00000000001", "success": True, "errors": []},
                {"id": "0PGC00000000002", "success": True, "errors": []},
            ],
        )

        task._run_task()

        assert len(responses.calls) == 3
        composite_request = json.loads(responses.calls[2].request.body)
        assert len(composite_request["records"]) == 2
        assert (
            composite_request["records"][0]["PermissionSetGroupId"] == "0PG000000000001"
        )
        assert composite_request["records"][0]["PermissionSetId"] == "0PS000000000001"

    @responses.activate
    def test_run_task_missing_psg(self):
        """Test _run_task with missing Permission Set Group"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"MissingPSG": ["PS1"]}},
        )
        task._init_task()

        # Mock PSG query - no results
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+DeveloperName%2C+NamespacePrefix+FROM+PermissionSetGroup+WHERE+%28DeveloperName+%3D+%27MissingPSG%27%29",
            status=200,
            json={"totalSize": 0, "done": True, "records": []},
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+Name%2C+NamespacePrefix+FROM+PermissionSet+WHERE+IsOwnedByProfile+%3D+false+AND+%28Name+%3D+%27PS1%27%29",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None}
                ],
            },
        )

        task._run_task()

        # Should not create any records since PSG is missing
        assert len(responses.calls) == 2
        # No composite API call should be made

    @responses.activate
    def test_run_task_missing_ps(self):
        """Test _run_task with missing Permission Set"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["MissingPS"]}},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+DeveloperName%2C+NamespacePrefix+FROM+PermissionSetGroup+WHERE+%28DeveloperName+%3D+%27PSG1%27%29",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        # Mock PS query - no results
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/?q=SELECT+Id%2C+Name%2C+NamespacePrefix+FROM+PermissionSet+WHERE+IsOwnedByProfile+%3D+false+AND+%28Name+%3D+%27MissingPS%27%29",
            status=200,
            json={"totalSize": 0, "done": True, "records": []},
        )

        task._run_task()

        # Should not create any records since PS is missing
        assert len(responses.calls) == 2
        # No composite API call should be made

    @responses.activate
    def test_run_task_batch_processing(self):
        """Test _run_task processes records in batches of 200"""
        # Create 250 assignments to test batching
        assignments = {}
        for i in range(250):
            psg_name = f"PSG{i // 10}"
            ps_name = f"PS{i}"
            if psg_name not in assignments:
                assignments[psg_name] = []
            assignments[psg_name].append(ps_name)

        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": assignments},
        )
        task._init_task()

        # Mock PSG query
        psg_records = [
            {"Id": f"0PG{i:012d}", "DeveloperName": f"PSG{i}", "NamespacePrefix": None}
            for i in range(25)
        ]
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={"totalSize": 25, "done": True, "records": psg_records},
        )

        # Mock PS query
        ps_records = [
            {"Id": f"0PS{i:012d}", "Name": f"PS{i}", "NamespacePrefix": None}
            for i in range(250)
        ]
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={"totalSize": 250, "done": True, "records": ps_records},
        )

        # Mock Composite API calls (2 batches: 200 + 50)
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {"id": f"0PGC{i:011d}", "success": True, "errors": []}
                for i in range(200)
            ],
        )
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {"id": f"0PGC{i:011d}", "success": True, "errors": []}
                for i in range(200, 250)
            ],
        )

        task._run_task()

        # Should have 2 composite API calls
        composite_calls = [
            call for call in responses.calls if "composite/sobjects" in call.request.url
        ]
        assert len(composite_calls) == 2
        assert len(json.loads(composite_calls[0].request.body)["records"]) == 200
        assert len(json.loads(composite_calls[1].request.body)["records"]) == 50

    def test_get_permission_set_group_ids_empty_list(self):
        """Test _get_permission_set_group_ids with empty list"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._get_permission_set_group_ids([])
        assert task.psg_ids == {}

    @responses.activate
    def test_get_permission_set_group_ids_success(self):
        """Test _get_permission_set_group_ids with successful query"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        task._get_permission_set_group_ids(["PSG1"])
        assert task.psg_ids["PSG1"] == "0PG000000000001"

    @responses.activate
    def test_get_permission_set_group_ids_with_namespace(self):
        """Test _get_permission_set_group_ids with namespace"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"NS__PSG1": ["PS1"]}, "namespace_inject": "NS"},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": "NS",
                    }
                ],
            },
        )

        task._get_permission_set_group_ids(["NS__PSG1"])
        assert "NS__PSG1" in task.psg_ids

    @responses.activate
    def test_get_permission_set_group_ids_query_error(self):
        """Test _get_permission_set_group_ids with query error"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=400,
            json=[{"errorCode": "INVALID_FIELD", "message": "Invalid field"}],
        )

        with pytest.raises(
            SalesforceException, match="Error querying Permission Set Groups"
        ):
            task._get_permission_set_group_ids(["PSG1"])

    def test_get_permission_set_ids_empty_list(self):
        """Test _get_permission_set_ids with empty list"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._get_permission_set_ids([])
        assert task.ps_ids == {}

    @responses.activate
    def test_get_permission_set_ids_success(self):
        """Test _get_permission_set_ids with successful query"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1", "PS2"]}},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 2,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None},
                    {"Id": "0PS000000000002", "Name": "PS2", "NamespacePrefix": None},
                ],
            },
        )

        task._get_permission_set_ids(["PS1", "PS2"])
        assert task.ps_ids["PS1"] == "0PS000000000001"
        assert task.ps_ids["PS2"] == "0PS000000000002"

    @responses.activate
    def test_get_permission_set_ids_removes_duplicates(self):
        """Test _get_permission_set_ids removes duplicates"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None}
                ],
            },
        )

        task._get_permission_set_ids(["PS1", "PS1", "PS1"])
        assert len(task.ps_ids) == 1
        assert task.ps_ids["PS1"] == "0PS000000000001"

    @responses.activate
    def test_get_permission_set_ids_with_namespace(self):
        """Test _get_permission_set_ids with namespace"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["NS__PS1"]}, "namespace_inject": "NS"},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": "NS"}
                ],
            },
        )

        task._get_permission_set_ids(["NS__PS1"])
        assert "NS__PS1" in task.ps_ids

    @responses.activate
    def test_get_permission_set_ids_query_error(self):
        """Test _get_permission_set_ids with query error"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()

        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=400,
            json=[{"errorCode": "INVALID_FIELD", "message": "Invalid field"}],
        )

        with pytest.raises(SalesforceException, match="Error querying Permission Sets"):
            task._get_permission_set_ids(["PS1"])

    def test_process_namespaces(self):
        """Test _process_namespaces"""
        with mock.patch(
            "cumulusci.tasks.salesforce.assign_ps_psg.inject_namespace",
            return_value=("", "NS__PS1"),
        ):
            task = create_task(
                AssignPermissionSetToPermissionSetGroup,
                {"assignments": {"PSG1": ["PS1"]}, "namespace_inject": "NS"},
            )
            task._init_options({})
            result = task._process_namespaces(["PS1"])
            assert result == {"PS1": "NS__PS1"}

    def test_build_name_conditions_no_namespace(self):
        """Test _build_name_conditions without namespace"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        conditions, mapping = task._build_name_conditions(["PS1"])
        assert len(conditions) == 1
        assert "Name = 'PS1'" in conditions[0]
        assert ("PS1", None) in mapping

    def test_build_name_conditions_with_namespace(self):
        """Test _build_name_conditions with namespace"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["NS__PS1"]}, "namespace_inject": "NS"},
        )
        task._init_options({})
        conditions, mapping = task._build_name_conditions(["NS__PS1"])
        assert len(conditions) == 1
        assert "NamespacePrefix = 'NS' AND Name = 'PS1'" in conditions[0]
        assert ("PS1", "NS") in mapping

    def test_build_name_conditions_with_escaped_quotes(self):
        """Test _build_name_conditions with names containing quotes"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS'1"]}},
        )
        task._init_options({})
        conditions, mapping = task._build_name_conditions(["PS'1"])
        assert "Name = 'PS''1'" in conditions[0]  # Single quote should be escaped

    def test_build_name_conditions_custom_field_name(self):
        """Test _build_name_conditions with custom field name"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        conditions, mapping = task._build_name_conditions(
            ["PS1"], field_name="DeveloperName"
        )
        assert "DeveloperName = 'PS1'" in conditions[0]

    @responses.activate
    def test_create_permission_set_group_components_success(self):
        """Test _create_permission_set_group_components with success"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()
        task.psg_ids = {"PSG1": "0PG000000000001"}
        task.ps_ids = {"PS1": "0PS000000000001"}

        records = [
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000001",
            }
        ]

        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[{"id": "0PGC00000000001", "success": True, "errors": []}],
        )

        task._create_permission_set_group_components(records)

        assert len(responses.calls) == 1
        request_body = json.loads(responses.calls[0].request.body)
        assert request_body["allOrNone"] is False
        assert len(request_body["records"]) == 1

    @responses.activate
    def test_create_permission_set_group_components_with_errors(self):
        """Test _create_permission_set_group_components with duplicate errors (should not raise exception)"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()
        task.psg_ids = {"PSG1": "0PG000000000001"}
        task.ps_ids = {"PS1": "0PS000000000001"}
        task.psg_names_sanitized = {"PSG1": "PSG1"}
        task.ps_names_sanitized = {"PS1": "PS1"}

        records = [
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000001",
            }
        ]

        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {
                    "id": None,
                    "success": False,
                    "errors": [
                        {"message": "Duplicate value", "statusCode": "DUPLICATE_VALUE"}
                    ],
                }
            ],
        )

        # Duplicate errors are now handled gracefully and should not raise an exception
        task._create_permission_set_group_components(records)
        assert len(responses.calls) == 1

    @responses.activate
    def test_create_permission_set_group_components_api_error(self):
        """Test _create_permission_set_group_components with API error"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()
        task.psg_ids = {"PSG1": "0PG000000000001"}
        task.ps_ids = {"PS1": "0PS000000000001"}

        records = [
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000001",
            }
        ]

        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=500,
            json=[{"errorCode": "INTERNAL_ERROR", "message": "Internal server error"}],
        )

        with pytest.raises(
            SalesforceException, match="Error creating PermissionSetGroupComponent"
        ):
            task._create_permission_set_group_components(records)

    @responses.activate
    def test_create_permission_set_group_components_non_list_response(self):
        """Test _create_permission_set_group_components with non-list response"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_options({})
        task._init_task()
        task.psg_ids = {"PSG1": "0PG000000000001"}
        task.ps_ids = {"PS1": "0PS000000000001"}

        records = [
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000001",
            }
        ]

        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json={"id": "0PGC00000000001", "success": True, "errors": []},
        )

        # Should handle non-list response gracefully
        task._create_permission_set_group_components(records)
        assert len(responses.calls) == 1

    @responses.activate
    def test_create_permission_set_group_components_partial_success(self):
        """Test _create_permission_set_group_components with partial success (should not raise exception for DUPLICATE_VALUE errors)"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1", "PS2"]}},
        )
        task._init_options({})
        task._init_task()
        task.psg_ids = {"PSG1": "0PG000000000001"}
        task.ps_ids = {"PS1": "0PS000000000001", "PS2": "0PS000000000002"}
        task.psg_names_sanitized = {"PSG1": "PSG1"}
        task.ps_names_sanitized = {"PS1": "PS1", "PS2": "PS2"}

        records = [
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000001",
            },
            {
                "attributes": {"type": "PermissionSetGroupComponent"},
                "PermissionSetGroupId": "0PG000000000001",
                "PermissionSetId": "0PS000000000002",
            },
        ]

        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {"id": "0PGC00000000001", "success": True, "errors": []},
                {
                    "id": None,
                    "success": False,
                    "errors": [
                        {"message": "Duplicate value", "statusCode": "DUPLICATE_VALUE"}
                    ],
                },
            ],
        )

        task._create_permission_set_group_components(records)
        assert len(responses.calls) == 1

    @responses.activate
    def test_run_task_multiple_psgs(self):
        """Test _run_task with multiple Permission Set Groups"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"], "PSG2": ["PS2"]}},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 2,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    },
                    {
                        "Id": "0PG000000000002",
                        "DeveloperName": "PSG2",
                        "NamespacePrefix": None,
                    },
                ],
            },
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 2,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None},
                    {"Id": "0PS000000000002", "Name": "PS2", "NamespacePrefix": None},
                ],
            },
        )

        # Mock Composite API
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=200,
            json=[
                {"id": "0PGC00000000001", "success": True, "errors": []},
                {"id": "0PGC00000000002", "success": True, "errors": []},
            ],
        )

        task._run_task()

        assert len(responses.calls) == 3
        composite_request = json.loads(responses.calls[2].request.body)
        assert len(composite_request["records"]) == 2

    @responses.activate
    def test_run_task_batch_error_with_fail_on_error_true(self):
        """Test _run_task raises exception when batch fails and fail_on_error=True"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}, "fail_on_error": True},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None}
                ],
            },
        )

        # Mock Composite API to raise an exception
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=500,
            json={"errorCode": "INTERNAL_ERROR", "message": "Internal server error"},
        )

        with pytest.raises(SalesforceException):
            task._run_task()

    @responses.activate
    def test_run_task_batch_error_with_fail_on_error_false(self):
        """Test _run_task continues when batch fails and fail_on_error=False"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}, "fail_on_error": False},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None}
                ],
            },
        )

        # Mock Composite API to raise an exception
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=500,
            json={"errorCode": "INTERNAL_ERROR", "message": "Internal server error"},
        )

        # Should not raise, just log the error
        task._run_task()

        # Verify that the error was logged (we can't easily test logging, but we can verify
        # that the task completed without raising)
        assert len(responses.calls) == 3

    @responses.activate
    def test_run_task_batch_error_with_fail_on_error_default(self):
        """Test _run_task continues when batch fails and fail_on_error is default (False)"""
        task = create_task(
            AssignPermissionSetToPermissionSetGroup,
            {"assignments": {"PSG1": ["PS1"]}},
        )
        task._init_task()

        # Mock PSG query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "Id": "0PG000000000001",
                        "DeveloperName": "PSG1",
                        "NamespacePrefix": None,
                    }
                ],
            },
        )

        # Mock PS query
        responses.add(
            method="GET",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/query/",
            status=200,
            json={
                "totalSize": 1,
                "done": True,
                "records": [
                    {"Id": "0PS000000000001", "Name": "PS1", "NamespacePrefix": None}
                ],
            },
        )

        # Mock Composite API to raise an exception
        responses.add(
            method="POST",
            url=f"{task.org_config.instance_url}/services/data/v{CURRENT_SF_API_VERSION}/composite/sobjects",
            status=500,
            json={"errorCode": "INTERNAL_ERROR", "message": "Internal server error"},
        )

        # Should not raise, just log the error (fail_on_error defaults to False)
        task._run_task()

        # Verify that the error was logged but task completed
        assert len(responses.calls) == 3
