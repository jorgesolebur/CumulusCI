from unittest import mock

import pytest

from cumulusci.core.exceptions import SalesforceException
from cumulusci.tasks.salesforce.update_record import UpdateRecord

from .util import create_task


class TestUpdateRecord:
    def test_run_task_with_record_id(self):
        """Test updating a single record by ID"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "values": "Name:UpdatedName,Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf  # Point api to mocked sf
        task.sf.Account.update.return_value = 204

        task._run_task()
        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX", {"Name": "UpdatedName", "Status__c": "Active"}
        )

    def test_run_task_with_record_id_dict_values(self):
        """Test updating with dict values instead of string"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "values": {"Name": "UpdatedName", "Active__c": True},
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.return_value = 204

        task._run_task()
        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX", {"Name": "UpdatedName", "Active__c": True}
        )

    def test_run_task_with_tooling_api(self):
        """Test using Tooling API"""
        task = create_task(
            UpdateRecord,
            {
                "object": "PermissionSet",
                "record_id": "0PS3D000000MKTqWAO",
                "values": "Label:UpdatedLabel",
                "tooling": True,
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.api = task.tooling
        task.tooling.PermissionSet.update.return_value = 204

        task._run_task()
        task.tooling.PermissionSet.update.assert_called_once_with(
            "0PS3D000000MKTqWAO", {"Label": "UpdatedLabel"}
        )

    def test_run_task_with_where_clause_single_record(self):
        """Test updating a single record found by query"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "where": "Name:TestAccount,Status__c:Draft",
                "values": "Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.return_value = {
            "records": [{"Id": "001xx000003DGbXXXX"}],
            "totalSize": 1,
        }
        task.sf.Account.update.return_value = 204

        task._run_task()

        # Verify query was executed
        task.sf.query.assert_called_once()
        query_arg = task.sf.query.call_args[0][0]
        assert "SELECT Id FROM Account WHERE" in query_arg
        assert "Name = 'TestAccount'" in query_arg
        assert "Status__c = 'Draft'" in query_arg

        # Verify update was called
        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX", {"Status__c": "Active"}
        )

    def test_run_task_with_where_clause_multiple_records(self):
        """Test updating multiple records found by query using bulk API"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Contact",
                "where": "Status__c:Draft",
                "values": "Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.return_value = {
            "records": [
                {"Id": "003xx000001Record1"},
                {"Id": "003xx000001Record2"},
                {"Id": "003xx000001Record3"},
            ],
            "totalSize": 3,
        }

        # Mock bulk API results
        task.bulk = mock.Mock()
        bulk_result = mock.Mock()
        bulk_result.success = True
        task.bulk.update.return_value = [bulk_result, bulk_result, bulk_result]

        task._run_task()

        # Verify bulk update was called with all records
        task.bulk.update.assert_called_once()
        call_args = task.bulk.update.call_args[0]
        assert call_args[0] == "Contact"
        assert len(call_args[1]) == 3
        assert call_args[1][0] == {"Id": "003xx000001Record1", "Status__c": "Active"}
        assert call_args[1][1] == {"Id": "003xx000001Record2", "Status__c": "Active"}
        assert call_args[1][2] == {"Id": "003xx000001Record3", "Status__c": "Active"}

    def test_run_task_no_records_found(self):
        """Test warning when no records are found"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "where": "Name:NonExistentAccount",
                "values": "Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.return_value = {"records": [], "totalSize": 0}

        # Should not raise an exception, just log a warning
        task._run_task()

        # Verify no updates were attempted
        task.sf.Account.update.assert_not_called()

    def test_run_task_partial_failure_with_fail_on_error_true(self):
        """Test that partial failures raise exception when fail_on_error=True using bulk API"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "where": "Status__c:Draft",
                "values": "Status__c:Active",
                "fail_on_error": True,
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.return_value = {
            "records": [
                {"Id": "001xx000001Record1"},
                {"Id": "001xx000001Record2"},
            ],
            "totalSize": 2,
        }

        # Mock bulk API: first succeeds, second fails
        task.bulk = mock.Mock()
        success_result = mock.Mock()
        success_result.success = True
        failure_result = mock.Mock()
        failure_result.success = False
        failure_result.error = "Update failed"
        task.bulk.update.return_value = [success_result, failure_result]

        with pytest.raises(SalesforceException) as exc_info:
            task._run_task()

        assert "Failed to update 1 record(s)" in str(exc_info.value)

    def test_run_task_partial_failure_with_fail_on_error_false(self):
        """Test that partial failures are logged when fail_on_error=False using bulk API"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "where": "Status__c:Draft",
                "values": "Status__c:Active",
                "fail_on_error": False,
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.return_value = {
            "records": [
                {"Id": "001xx000001Record1"},
                {"Id": "001xx000001Record2"},
            ],
            "totalSize": 2,
        }

        # Mock bulk API: first succeeds, second fails
        task.bulk = mock.Mock()
        success_result = mock.Mock()
        success_result.success = True
        failure_result = mock.Mock()
        failure_result.success = False
        failure_result.error = "Update failed"
        task.bulk.update.return_value = [success_result, failure_result]

        # Should not raise an exception
        task._run_task()

        # Verify bulk update was called
        task.bulk.update.assert_called_once()

    def test_run_task_update_by_id_with_fail_on_error_false(self):
        """Test that update by ID with error doesn't raise when fail_on_error=False"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "values": "Name:UpdatedName",
                "fail_on_error": False,
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.side_effect = Exception("Update failed")

        # Should not raise an exception
        task._run_task()

        # Verify update was attempted
        task.sf.Account.update.assert_called_once()

    def test_missing_record_id_and_where(self):
        """Test that missing both record_id and where raises exception"""
        with pytest.raises(SalesforceException) as exc_info:
            create_task(
                UpdateRecord,
                {
                    "object": "Account",
                    "values": "Name:UpdatedName",
                },
            )
        assert "Either 'record_id' or 'where' option must be specified" in str(
            exc_info.value
        )

    def test_record_id_ignores_where(self):
        """Test that record_id takes precedence over where clause"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "where": "Name:TestAccount",
                "values": "Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.return_value = 204

        task._run_task()

        # Verify query was NOT called
        task.sf.query.assert_not_called()

        # Verify direct update was called
        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX", {"Status__c": "Active"}
        )

    def test_salesforce_error_update_by_id(self):
        """Test Salesforce error when updating by ID with fail_on_error=True"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "values": "Name:UpdatedName",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.side_effect = Exception("Invalid field")

        with pytest.raises(SalesforceException) as exc_info:
            task._run_task()

        assert "Error updating Account record" in str(exc_info.value)

    def test_query_error(self):
        """Test error during query execution"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "where": "Name:TestAccount",
                "values": "Status__c:Active",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.query.side_effect = Exception("Invalid query")

        with pytest.raises(SalesforceException) as exc_info:
            task._run_task()

        assert "Error executing query" in str(exc_info.value)

    def test_update_with_dict_response(self):
        """Test handling dict response from simple_salesforce"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "values": "Name:UpdatedName",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.return_value = {"success": True}

        task._run_task()

        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX", {"Name": "UpdatedName"}
        )

    def test_missing_values_and_transform_values(self):
        """Test that missing both values and transform_values raises exception"""
        with pytest.raises(SalesforceException) as exc_info:
            create_task(
                UpdateRecord,
                {
                    "object": "Account",
                    "record_id": "001xx000003DGbXXXX",
                },
            )
        assert "Either 'values' or 'transform_values' option must be specified" in str(
            exc_info.value
        )

    def test_transform_values_with_env_vars(self):
        """Test transform_values extracts values from environment variables"""
        import os

        # Set environment variables
        os.environ["TEST_ACCOUNT_NAME"] = "TestAccountFromEnv"
        os.environ["TEST_STATUS"] = "ActiveFromEnv"

        try:
            task = create_task(
                UpdateRecord,
                {
                    "object": "Account",
                    "record_id": "001xx000003DGbXXXX",
                    "transform_values": "Name:TEST_ACCOUNT_NAME,Status__c:TEST_STATUS",
                },
            )
            task._init_task()
            task.sf = mock.Mock()
            task.api = task.sf
            task.sf.Account.update.return_value = 204

            task._run_task()

            # Verify the update was called with environment variable values
            task.sf.Account.update.assert_called_once_with(
                "001xx000003DGbXXXX",
                {"Name": "TestAccountFromEnv", "Status__c": "ActiveFromEnv"},
            )
        finally:
            # Clean up environment variables
            del os.environ["TEST_ACCOUNT_NAME"]
            del os.environ["TEST_STATUS"]

    def test_transform_values_with_missing_env_vars(self):
        """Test transform_values defaults to key name when env var doesn't exist"""
        task = create_task(
            UpdateRecord,
            {
                "object": "Account",
                "record_id": "001xx000003DGbXXXX",
                "transform_values": "Name:NONEXISTENT_VAR,Status__c:ANOTHER_MISSING_VAR",
            },
        )
        task._init_task()
        task.sf = mock.Mock()
        task.api = task.sf
        task.sf.Account.update.return_value = 204

        task._run_task()

        # Verify the update was called with the key names as defaults
        task.sf.Account.update.assert_called_once_with(
            "001xx000003DGbXXXX",
            {"Name": "NONEXISTENT_VAR", "Status__c": "ANOTHER_MISSING_VAR"},
        )

    def test_values_and_transform_values_combined(self):
        """Test that values and transform_values can be combined, with transform_values overriding"""
        import os

        os.environ["TEST_OVERRIDE_NAME"] = "OverriddenName"

        try:
            task = create_task(
                UpdateRecord,
                {
                    "object": "Account",
                    "record_id": "001xx000003DGbXXXX",
                    "values": "Name:OriginalName,Type:Customer",
                    "transform_values": "Name:TEST_OVERRIDE_NAME",
                },
            )
            task._init_task()
            task.sf = mock.Mock()
            task.api = task.sf
            task.sf.Account.update.return_value = 204

            task._run_task()

            # Verify transform_values overrides values for Name, but Type remains
            task.sf.Account.update.assert_called_once_with(
                "001xx000003DGbXXXX",
                {"Name": "OverriddenName", "Type": "Customer"},
            )
        finally:
            del os.environ["TEST_OVERRIDE_NAME"]

    def test_transform_values_with_where_clause(self):
        """Test transform_values works with where clause for multiple records using bulk API"""
        import os

        os.environ["TEST_STATUS_VALUE"] = "Completed"

        try:
            task = create_task(
                UpdateRecord,
                {
                    "object": "Account",
                    "where": "Type:Customer",
                    "transform_values": "Status__c:TEST_STATUS_VALUE",
                },
            )
            task._init_task()
            task.sf = mock.Mock()
            task.api = task.sf
            task.sf.query.return_value = {
                "records": [
                    {"Id": "001xx000001Record1"},
                    {"Id": "001xx000001Record2"},
                ],
                "totalSize": 2,
            }

            # Mock bulk API
            task.bulk = mock.Mock()
            bulk_result = mock.Mock()
            bulk_result.success = True
            task.bulk.update.return_value = [bulk_result, bulk_result]

            task._run_task()

            # Verify bulk update was called with environment variable values
            task.bulk.update.assert_called_once()
            call_args = task.bulk.update.call_args[0]
            assert call_args[0] == "Account"
            assert len(call_args[1]) == 2
            assert call_args[1][0] == {
                "Id": "001xx000001Record1",
                "Status__c": "Completed",
            }
            assert call_args[1][1] == {
                "Id": "001xx000001Record2",
                "Status__c": "Completed",
            }
        finally:
            del os.environ["TEST_STATUS_VALUE"]
