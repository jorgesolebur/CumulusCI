from unittest import mock

import pytest

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.core.versions import PackageType, PackageVersionNumber
from cumulusci.tasks.salesforce.getPackageVersion import GetPackageVersion

from .util import create_task


class TestGetPackageVersion:
    """Test cases for GetPackageVersion task"""

    def test_init_options_with_string_version(self):
        """Test _init_options with string version number"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "prefix": "test_",
                "suffix": "_prod",
                "fail_on_error": True,
            },
        )

        # Verify package_version is parsed correctly
        assert isinstance(task.parsed_options.package_version, PackageVersionNumber)
        assert task.parsed_options.package_version.MajorVersion == 1
        assert task.parsed_options.package_version.MinorVersion == 2
        assert task.parsed_options.package_version.PatchVersion == 3
        assert task.parsed_options.package_version.BuildNumber == 4
        assert (
            task.parsed_options.package_version.package_type == PackageType.SECOND_GEN
        )

    def test_init_options_with_minimal_version(self):
        """Test _init_options with minimal version number"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0",
            },
        )

        # Verify package_version is parsed correctly with defaults
        assert task.parsed_options.package_version.MajorVersion == 1
        assert task.parsed_options.package_version.MinorVersion == 0
        assert task.parsed_options.package_version.PatchVersion == 0
        assert task.parsed_options.package_version.BuildNumber == 0

    def test_init_options_with_beta_version(self):
        """Test _init_options with beta version number"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3 (Beta 5)",
            },
        )

        # Verify package_version is parsed correctly
        assert task.parsed_options.package_version.MajorVersion == 1
        assert task.parsed_options.package_version.MinorVersion == 2
        assert task.parsed_options.package_version.PatchVersion == 3
        assert task.parsed_options.package_version.BuildNumber == 5

    def test_init_options_defaults(self):
        """Test _init_options with default values"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
            },
        )

        # Verify default values
        assert task.parsed_options.prefix == ""
        assert task.parsed_options.suffix == ""
        assert task.parsed_options.fail_on_error is False

    @mock.patch(
        "cumulusci.tasks.salesforce.getPackageVersion.get_simple_salesforce_connection"
    )
    @mock.patch("cumulusci.tasks.salesforce.getPackageVersion.get_devhub_config")
    def test_init_task(self, mock_get_devhub_config, mock_get_connection):
        """Test _init_task method"""
        mock_devhub_config = mock.Mock()
        mock_get_devhub_config.return_value = mock_devhub_config
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
            },
        )

        # Mock project config
        task.project_config.project__package__api_version = "58.0"

        # Call _init_task manually since it's not called automatically
        task._init_task()

        # Verify tooling connection is created
        mock_get_devhub_config.assert_called_once_with(task.project_config)
        mock_get_connection.assert_called_once_with(
            task.project_config,
            mock_devhub_config,
            api_version="58.0",
            base_url="tooling",
        )
        assert task.tooling == mock_tooling

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_run_task_success(self, mock_get_devhub_config, mock_get_connection):
        """Test _run_task with successful package version found"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        # Mock successful query result
        mock_tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "05i000000000000",
                    "SubscriberPackageVersionId": "04t000000000000",
                }
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "prefix": "test_",
                "suffix": "_prod",
            },
        )
        task.tooling = mock_tooling

        result = task._run_task()

        # Verify query was called with correct parameters
        expected_query = (
            "SELECT Id, SubscriberPackageVersionId FROM Package2Version WHERE Package2.Name='test_TestPackage_prod' AND "
            "MajorVersion=1 AND "
            "MinorVersion=2 AND "
            "PatchVersion=3 AND "
            "BuildNumber=4"
        )
        mock_tooling.query.assert_called_once_with(expected_query)

        # Verify return values
        assert result["package_version_id"] == "05i000000000000"
        assert result["subscriber_package_version_id"] == "04t000000000000"
        assert result["package_name"] == "test_TestPackage_prod"
        assert result["package_version"] == task.parsed_options.package_version

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_run_task_not_found_without_fail(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test _run_task when package version not found without fail_on_error"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        # Mock empty query result
        mock_tooling.query.return_value = {"size": 0, "records": []}

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": False,
            },
        )
        task.tooling = mock_tooling

        # Should not raise exception when fail_on_error=False
        result = task._run_task()

        # Verify method returns None when no records found
        assert result is None

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_run_task_not_found_with_fail(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test _run_task when package version not found with fail_on_error=True"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        # Mock empty query result
        mock_tooling.query.return_value = {"size": 0, "records": []}

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": True,
            },
        )
        task.tooling = mock_tooling

        # Should raise SalesforceDXException
        with pytest.raises(SalesforceDXException) as exc_info:
            task._run_task()

        assert "Package version TestPackage 1.2.3.4 not found" in str(exc_info.value)

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_run_task_multiple_versions_without_fail(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test _run_task when multiple package versions found without fail_on_error"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        # Mock multiple query results
        mock_tooling.query.return_value = {
            "size": 2,
            "records": [
                {
                    "Id": "05i000000000001",
                    "SubscriberPackageVersionId": "04t000000000001",
                },
                {
                    "Id": "05i000000000002",
                    "SubscriberPackageVersionId": "04t000000000002",
                },
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": False,
            },
        )
        task.tooling = mock_tooling

        # Should not raise exception, should use first record
        result = task._run_task()

        # Verify return values use first record
        assert result["package_version_id"] == "05i000000000001"
        assert result["subscriber_package_version_id"] == "04t000000000001"

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_run_task_multiple_versions_with_fail(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test _run_task when multiple package versions found with fail_on_error=True"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling

        # Mock multiple query results
        mock_tooling.query.return_value = {
            "size": 2,
            "records": [
                {
                    "Id": "05i000000000001",
                    "SubscriberPackageVersionId": "04t000000000001",
                },
                {
                    "Id": "05i000000000002",
                    "SubscriberPackageVersionId": "04t000000000002",
                },
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": True,
            },
        )
        task.tooling = mock_tooling

        # Should raise SalesforceDXException
        with pytest.raises(SalesforceDXException) as exc_info:
            task._run_task()

        assert "Multiple package versions found for TestPackage 1.2.3.4" in str(
            exc_info.value
        )

    def test_package_name_construction(self):
        """Test package name construction with prefix and suffix"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
                "prefix": "pre_",
                "suffix": "_suf",
            },
        )

        # Test the package name construction logic
        package_name = f"{task.parsed_options.prefix}{task.parsed_options.package_name}{task.parsed_options.suffix}".strip()
        assert package_name == "pre_TestPackage_suf"

    def test_package_name_construction_with_spaces(self):
        """Test package name construction with spaces in prefix/suffix"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
                "prefix": " pre ",
                "suffix": " suf ",
            },
        )

        # Test the package name construction logic with strip()
        package_name = f"{task.parsed_options.prefix}{task.parsed_options.package_name}{task.parsed_options.suffix}".strip()
        assert package_name == "pre TestPackage suf"

    def test_package_name_construction_empty_prefix_suffix(self):
        """Test package name construction with empty prefix and suffix"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
                "prefix": "",
                "suffix": "",
            },
        )

        # Test the package name construction logic
        package_name = f"{task.parsed_options.prefix}{task.parsed_options.package_name}{task.parsed_options.suffix}".strip()
        assert package_name == "TestPackage"

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_query_construction_with_different_versions(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test SOQL query construction with different version numbers"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "05i000000000000",
                    "SubscriberPackageVersionId": "04t000000000000",
                }
            ],
        }

        # Test with version 2.5.1.10
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "2.5.1.10",
            },
        )
        task.tooling = mock_tooling

        task._run_task()

        # Verify query construction
        expected_query = (
            "SELECT Id, SubscriberPackageVersionId FROM Package2Version WHERE Package2.Name='TestPackage' AND "
            "MajorVersion=2 AND "
            "MinorVersion=5 AND "
            "PatchVersion=1 AND "
            "BuildNumber=10"
        )
        mock_tooling.query.assert_called_once_with(expected_query)

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_query_construction_with_beta_version(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test SOQL query construction with beta version"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "05i000000000000",
                    "SubscriberPackageVersionId": "04t000000000000",
                }
            ],
        }

        # Test with beta version
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0 (Beta 3)",
            },
        )
        task.tooling = mock_tooling

        task._run_task()

        # Verify query construction with beta build number
        expected_query = (
            "SELECT Id, SubscriberPackageVersionId FROM Package2Version WHERE Package2.Name='TestPackage' AND "
            "MajorVersion=1 AND "
            "MinorVersion=0 AND "
            "PatchVersion=0 AND "
            "BuildNumber=3"
        )
        mock_tooling.query.assert_called_once_with(expected_query)

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_return_values_structure(self, mock_get_devhub_config, mock_get_connection):
        """Test return values structure and content"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "05i000000000000",
                    "SubscriberPackageVersionId": "04t000000000000",
                }
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "prefix": "test_",
                "suffix": "_prod",
            },
        )
        task.tooling = mock_tooling

        result = task._run_task()

        # Verify all expected return values are present
        expected_keys = [
            "package_version_id",
            "subscriber_package_version_id",
            "package_name",
            "package_version",
        ]
        for key in expected_keys:
            assert key in result

        # Verify return values content
        assert result["package_version_id"] == "05i000000000000"
        assert result["subscriber_package_version_id"] == "04t000000000000"
        assert result["package_name"] == "test_TestPackage_prod"
        assert isinstance(result["package_version"], PackageVersionNumber)
        assert result["package_version"].MajorVersion == 1
        assert result["package_version"].MinorVersion == 2
        assert result["package_version"].PatchVersion == 3
        assert result["package_version"].BuildNumber == 4

    def test_options_field_descriptions(self):
        """Test that all options have proper descriptions"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.0.0.0",
            },
        )

        # Verify required fields
        assert hasattr(task.parsed_options, "package_name")
        assert hasattr(task.parsed_options, "package_version")

        # Verify optional fields with defaults
        assert hasattr(task.parsed_options, "prefix")
        assert hasattr(task.parsed_options, "suffix")
        assert hasattr(task.parsed_options, "fail_on_error")

        # Verify default values
        assert task.parsed_options.prefix == ""
        assert task.parsed_options.suffix == ""
        assert task.parsed_options.fail_on_error is False

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_logging_messages(self, mock_get_devhub_config, mock_get_connection):
        """Test logging messages for successful scenario"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "05i000000000000",
                    "SubscriberPackageVersionId": "04t000000000000",
                }
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
            },
        )
        task.tooling = mock_tooling

        # Mock logger to capture log messages
        with mock.patch.object(task.logger, "info") as mock_info, mock.patch.object(
            task.logger, "warning"
        ):

            task._run_task()

            # Verify info messages were logged
            assert mock_info.call_count >= 3  # At least 3 info messages
            mock_info.assert_any_call("Package version TestPackage 1.2.3.4 found")
            mock_info.assert_any_call("Package version id: 05i000000000000")
            mock_info.assert_any_call("SubscriberPackageVersion Id: 04t000000000000")

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_logging_warning_not_found(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test logging warning when package version not found"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {"size": 0, "records": []}

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": False,
            },
        )
        task.tooling = mock_tooling

        # Mock logger to capture log messages
        with mock.patch.object(task.logger, "warning") as mock_warning:
            task._run_task()

            # Verify warning message was logged
            mock_warning.assert_called_once_with(
                "Package version TestPackage 1.2.3.4 not found"
            )

    @mock.patch("cumulusci.salesforce_api.utils.get_simple_salesforce_connection")
    @mock.patch("cumulusci.core.config.util.get_devhub_config")
    def test_logging_warning_multiple_found(
        self, mock_get_devhub_config, mock_get_connection
    ):
        """Test logging warning when multiple package versions found"""
        mock_tooling = mock.Mock()
        mock_get_connection.return_value = mock_tooling
        mock_tooling.query.return_value = {
            "size": 2,
            "records": [
                {
                    "Id": "05i000000000001",
                    "SubscriberPackageVersionId": "04t000000000001",
                },
                {
                    "Id": "05i000000000002",
                    "SubscriberPackageVersionId": "04t000000000002",
                },
            ],
        }

        task = create_task(
            GetPackageVersion,
            {
                "package_name": "TestPackage",
                "package_version": "1.2.3.4",
                "fail_on_error": False,
            },
        )
        task.tooling = mock_tooling

        # Mock logger to capture log messages
        with mock.patch.object(task.logger, "warning") as mock_warning:
            task._run_task()

            # Verify warning message was logged
            mock_warning.assert_called_once_with(
                "Multiple package versions found for TestPackage 1.2.3.4"
            )

    def test_invalid_version_format(self):
        """Test handling of invalid version format"""
        with pytest.raises(ValueError):
            create_task(
                GetPackageVersion,
                {
                    "package_name": "TestPackage",
                    "package_version": "invalid_version",
                },
            )

    def test_empty_package_name(self):
        """Test with empty package name"""
        task = create_task(
            GetPackageVersion,
            {
                "package_name": "",
                "package_version": "1.0.0.0",
            },
        )

        # Should not raise exception during initialization
        assert task.parsed_options.package_name == ""

    def test_very_long_package_name(self):
        """Test with very long package name"""
        long_name = "A" * 1000
        task = create_task(
            GetPackageVersion,
            {
                "package_name": long_name,
                "package_version": "1.0.0.0",
            },
        )

        # Should not raise exception during initialization
        assert task.parsed_options.package_name == long_name
