import re
from unittest import mock

import pytest
import responses

from cumulusci.core.exceptions import SalesforceException
from cumulusci.tasks.salesforce.insert_record import InsertRecord
from cumulusci.tests.util import CURRENT_SF_API_VERSION

from .util import create_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUCCESS_RC = {"id": "0PS3D000000MKTqWAO", "success": True, "errors": []}
FAILURE_RC = {
    "success": False,
    "errors": [
        {"errorCode": "NOT_FOUND", "message": "The requested resource does not exist"}
    ],
}


def _task(options):
    """Shortcut: create an InsertRecord task with the given options."""
    return create_task(InsertRecord, options)


def _mock_sf(task, insert_return=None, query_return=None):
    """Replace task.sf with a Mock, wiring up common return values."""
    task.sf = mock.MagicMock()
    if insert_return is not None:
        task.sf.Contact.create.return_value = insert_return
        task.sf.PermissionSet.create.return_value = insert_return
    if query_return is not None:
        task.sf.query.return_value = query_return
    return task.sf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInsertRecord:

    # ------------------------------------------------------------------
    # Options / Validation
    # ------------------------------------------------------------------

    def test_missing_both_values_and_lookup_values_raises(self):
        """Neither values nor lookupValues provided → SalesforceException."""
        with pytest.raises(SalesforceException) as exc_info:
            _task({"object": "Contact"})
        assert "Either 'values' or 'lookupValues' option must be specified" in str(
            exc_info.value
        )

    def test_values_only_is_valid(self):
        """values alone is sufficient."""
        task = _task({"object": "Contact", "values": "LastName:Smith"})
        assert task.parsed_options.values == {"LastName": "Smith"}
        assert task.parsed_options.lookupValues is None

    def test_lookup_values_only_is_valid(self):
        """lookupValues alone (no values) is sufficient."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    }
                },
            }
        )
        assert task.parsed_options.values is None
        assert "AccountId" in task.parsed_options.lookupValues

    def test_both_values_and_lookup_values_is_valid(self):
        """Providing both values and lookupValues is valid."""
        task = _task(
            {
                "object": "Contact",
                "values": "LastName:Smith",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    }
                },
            }
        )
        assert task.parsed_options.values == {"LastName": "Smith"}
        assert task.parsed_options.lookupValues is not None

    # ------------------------------------------------------------------
    # Static values - existing behaviour preserved
    # ------------------------------------------------------------------

    def test_run_task_static_values(self):
        """Insert using string-format values uses REST API."""
        task = _task(
            {
                "object": "PermissionSet",
                "values": "Name:HardDelete,PermissionsBulkApiHardDelete:true",
            }
        )
        task.sf = mock.Mock()
        task.sf.PermissionSet.create.return_value = SUCCESS_RC

        task._run_task()

        task.sf.PermissionSet.create.assert_called_once_with(
            {"Name": "HardDelete", "PermissionsBulkApiHardDelete": "true"}
        )

    def test_run_task_dict_tooling(self):
        """Insert using dict values via Tooling API."""
        task = _task(
            {
                "object": "PermissionSet",
                "tooling": True,
                "values": {"Name": "HardDelete", "PermissionsBulkApiHardDelete": True},
            }
        )
        task.tooling = mock.Mock()
        task.tooling.PermissionSet.create.return_value = SUCCESS_RC

        task._run_task()

        task.tooling.PermissionSet.create.assert_called_once_with(
            {"Name": "HardDelete", "PermissionsBulkApiHardDelete": True}
        )

    # ------------------------------------------------------------------
    # lookupValues resolution
    # ------------------------------------------------------------------

    def test_run_task_lookup_values_only(self):
        """lookupValues resolves the field and inserts with the looked-up id."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    }
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": [{"Id": "001ACME0000001"}]}
        task.sf.Contact.create.return_value = SUCCESS_RC

        task._run_task()

        task.sf.query.assert_called_once_with(
            "SELECT Id FROM Account WHERE Name = 'Acme'"
        )
        task.sf.Contact.create.assert_called_once_with({"AccountId": "001ACME0000001"})

    def test_run_task_values_and_lookup_values_merged(self):
        """Static values and resolved lookupValues are merged before insert."""
        task = _task(
            {
                "object": "Contact",
                "values": "LastName:Smith",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    }
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": [{"Id": "001ACME0000001"}]}
        task.sf.Contact.create.return_value = SUCCESS_RC

        task._run_task()

        task.sf.Contact.create.assert_called_once_with(
            {"LastName": "Smith", "AccountId": "001ACME0000001"}
        )

    def test_run_task_lookup_values_multiple_fields(self):
        """Multiple lookupValues entries are all resolved and merged."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    },
                    "ReportsToId": {
                        "field": "Id",
                        "object": "Contact",
                        "where": "Email = 'mgr@acme.com'",
                    },
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.side_effect = [
            {"records": [{"Id": "001ACME0000001"}]},
            {"records": [{"Id": "003MGR00000001"}]},
        ]
        task.sf.Contact.create.return_value = SUCCESS_RC

        task._run_task()

        task.sf.Contact.create.assert_called_once_with(
            {"AccountId": "001ACME0000001", "ReportsToId": "003MGR00000001"}
        )

    def test_run_task_lookup_via_tooling_api(self):
        """lookupValues resolution uses the Tooling API when tooling=True."""
        task = _task(
            {
                "object": "ApexClass",
                "tooling": True,
                "lookupValues": {
                    "NamespaceId": {
                        "field": "Id",
                        "object": "PackageVersion",
                        "where": "Name = 'MyPkg'",
                    }
                },
            }
        )
        task.tooling = mock.MagicMock()
        task.tooling.query.return_value = {"records": [{"Id": "033PKG0000001"}]}
        task.tooling.ApexClass.create.return_value = SUCCESS_RC

        task._run_task()

        task.tooling.query.assert_called_once_with(
            "SELECT Id FROM PackageVersion WHERE Name = 'MyPkg'"
        )
        task.tooling.ApexClass.create.assert_called_once_with(
            {"NamespaceId": "033PKG0000001"}
        )

    def test_lookup_non_id_field_resolved(self):
        """lookupValues can resolve fields other than Id."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "Department": {
                        "field": "DepartmentCode__c",
                        "object": "Department__c",
                        "where": "Name = 'Engineering'",
                    }
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": [{"DepartmentCode__c": "ENG"}]}
        task.sf.Contact.create.return_value = SUCCESS_RC

        task._run_task()

        task.sf.Contact.create.assert_called_once_with({"Department": "ENG"})

    # ------------------------------------------------------------------
    # _resolve_lookup_values – edge / error cases
    # ------------------------------------------------------------------

    def test_lookup_no_records_raises(self):
        """Lookup returning zero records always raises SalesforceException."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'MISSING'",
                    }
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": []}

        with pytest.raises(SalesforceException, match="returned no records"):
            task._run_task()

    def test_lookup_multiple_records_fail_on_multiple_true(self):
        """fail_on_multiple_records=True → raise when >1 record returned."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "BillingState = 'CA'",
                    }
                },
                "fail_on_multiple_records": True,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": [{"Id": "001AAA"}, {"Id": "001BBB"}]}

        with pytest.raises(SalesforceException, match="returned 2 records"):
            task._run_task()

    def test_lookup_multiple_records_fail_on_multiple_false_uses_first(self):
        """fail_on_multiple_records=False (default) → warn and use first record."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "BillingState = 'CA'",
                    }
                },
                "fail_on_multiple_records": False,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.return_value = {"records": [{"Id": "001AAA"}, {"Id": "001BBB"}]}
        task.sf.Contact.create.return_value = SUCCESS_RC

        task._run_task()

        # Must use the FIRST record
        task.sf.Contact.create.assert_called_once_with({"AccountId": "001AAA"})

    def test_lookup_query_exception_raises(self):
        """An exception during the lookup query is re-raised as SalesforceException."""
        task = _task(
            {
                "object": "Contact",
                "lookupValues": {
                    "AccountId": {
                        "field": "Id",
                        "object": "Account",
                        "where": "Name = 'Acme'",
                    }
                },
            }
        )
        task.sf = mock.MagicMock()
        task.sf.query.side_effect = RuntimeError("network error")

        with pytest.raises(SalesforceException, match="Error executing lookup query"):
            task._run_task()

    # ------------------------------------------------------------------
    # fail_on_error
    # ------------------------------------------------------------------

    def test_fail_on_error_true_raises_on_insert_exception(self):
        """fail_on_error=True (default) re-raises insert exceptions as SalesforceException."""
        task = _task(
            {
                "object": "Contact",
                "values": "LastName:Smith",
                "fail_on_error": True,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.Contact.create.side_effect = RuntimeError("API unavailable")

        with pytest.raises(SalesforceException, match="Error inserting Contact record"):
            task._run_task()

    def test_fail_on_error_false_logs_warning_on_insert_exception(self):
        """fail_on_error=False logs a warning instead of raising on insert exception."""
        task = _task(
            {
                "object": "Contact",
                "values": "LastName:Smith",
                "fail_on_error": False,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.Contact.create.side_effect = RuntimeError("API unavailable")

        # Should not raise
        task._run_task()

        # Insert was attempted
        task.sf.Contact.create.assert_called_once()

    def test_fail_on_error_true_raises_on_success_false(self):
        """success=False response raises SalesforceException when fail_on_error=True."""
        task = _task(
            {
                "object": "PermissionSet",
                "values": "Name:HardDelete,PermissionsBulkApiHardDelete:true",
                "fail_on_error": True,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.PermissionSet.create.return_value = FAILURE_RC

        with pytest.raises(
            SalesforceException, match="Could not insert PermissionSet record"
        ):
            task._run_task()

    def test_fail_on_error_false_logs_warning_on_success_false(self):
        """success=False response logs a warning when fail_on_error=False."""
        task = _task(
            {
                "object": "PermissionSet",
                "values": "Name:HardDelete",
                "fail_on_error": False,
            }
        )
        task.sf = mock.MagicMock()
        task.sf.PermissionSet.create.return_value = FAILURE_RC

        # Should not raise
        task._run_task()

        task.sf.PermissionSet.create.assert_called_once()

    # ------------------------------------------------------------------
    # Backward-compatibility – original test scenarios
    # ------------------------------------------------------------------

    def test_salesforce_error_returned_by_simple_salesforce(self):
        """success=False (simple_salesforce doesn't raise) → SalesforceException raised."""
        task = _task(
            {
                "object": "PermissionSet",
                "values": "Name:HardDelete,PermissionsBulkApiHardDelete:true",
            }
        )
        task.sf = mock.Mock()
        task.sf.PermissionSet.create.return_value = FAILURE_RC

        with pytest.raises(SalesforceException):
            task._run_task()

    @responses.activate
    def test_salesforce_error_raised_by_simple_salesforce(self):
        """HTTP error from simple_salesforce is caught and re-raised as SalesforceException."""
        task = _task(
            {
                "object": "PermissionSet",
                "values": "Name:HardDelete,PermissionsBulkApiHardDelete:true",
            }
        )
        responses.add(
            responses.POST,
            re.compile(
                rf"https://test.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}/.*"
            ),
            content_type="application/json",
            status=404,
            json=FAILURE_RC,
        )
        task._init_task()

        with pytest.raises(SalesforceException):
            task._run_task()
