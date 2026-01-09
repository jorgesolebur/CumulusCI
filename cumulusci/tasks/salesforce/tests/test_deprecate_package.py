from unittest import mock

import pytest
from simple_salesforce.exceptions import SalesforceMalformedRequest

from cumulusci.core.exceptions import SalesforceException, TaskOptionsError
from cumulusci.tasks.salesforce.deprecate_package import DeprecatePackage

from .util import create_task


class TestDeprecatePackage:
    def test_init_task(self):
        """Test task initialization"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        assert task.tooling is not None

    def test_init_task_without_org_uses_devhub(self):
        """Test task initialization without org uses devhub"""
        from cumulusci.core.config import TaskConfig
        from cumulusci.tests.util import create_project_config

        project_config = create_project_config()
        task_config = TaskConfig({"options": {"package": "0Ho000000000000AAA"}})
        task = DeprecatePackage(
            project_config,
            task_config,
            org_config=None,
        )

        with mock.patch(
            "cumulusci.tasks.salesforce.deprecate_package.get_devhub_config"
        ) as mock_get_devhub:
            with mock.patch.object(task, "_init_api", return_value=mock.Mock()):
                with mock.patch.object(task, "_init_bulk", return_value=mock.Mock()):
                    mock_devhub_config = mock.Mock()
                    mock_get_devhub.return_value = mock_devhub_config
                    task._init_task()

                    mock_get_devhub.assert_called_once_with(project_config)
                    assert task.org_config == mock_devhub_config

    def test_init_task_with_org_uses_provided_org(self):
        """Test task initialization with org uses provided org"""
        from cumulusci.core.config import TaskConfig
        from cumulusci.core.config.org_config import OrgConfig
        from cumulusci.tests.util import DummyKeychain, create_project_config

        project_config = create_project_config()
        task_config = TaskConfig({"options": {"package": "0Ho000000000000AAA"}})
        provided_org = OrgConfig(
            {
                "instance_url": "https://test.salesforce.com",
                "id": "https://test.salesforce.com/ORG_ID/USER_ID",
                "access_token": "TOKEN",
                "org_id": "ORG_ID",
                "username": "test-cci@example.com",
            },
            "test",
            keychain=DummyKeychain(),
        )
        task = DeprecatePackage(
            project_config,
            task_config,
            org_config=provided_org,
        )

        with mock.patch(
            "cumulusci.tasks.salesforce.deprecate_package.get_devhub_config"
        ) as mock_get_devhub:
            task._init_task()

            # Should not call get_devhub_config when org is provided
            mock_get_devhub.assert_not_called()
            assert task.org_config == provided_org

    def test_get_package_by_id_success(self):
        """Test getting package by Id"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "0Ho000000000000AAA",
                    "Name": "TestPackage",
                    "ContainerOptions": "Unlocked",
                    "IsDeprecated": False,
                }
            ],
        }

        result = task._get_package("0Ho000000000000AAA")
        assert result["Id"] == "0Ho000000000000AAA"
        assert result["Name"] == "TestPackage"
        task.tooling.query.assert_called_once()
        assert "Id='0Ho000000000000AAA'" in task.tooling.query.call_args[0][0]

    def test_get_package_by_name_success(self):
        """Test getting package by Name"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "TestPackage",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {
            "size": 1,
            "records": [
                {
                    "Id": "0Ho000000000000AAA",
                    "Name": "TestPackage",
                    "ContainerOptions": "Unlocked",
                    "IsDeprecated": False,
                }
            ],
        }

        result = task._get_package("TestPackage")
        assert result["Id"] == "0Ho000000000000AAA"
        assert result["Name"] == "TestPackage"
        assert "Name='TestPackage'" in task.tooling.query.call_args[0][0]
        assert "IsDeprecated = FALSE" in task.tooling.query.call_args[0][0]

    def test_get_package_not_found(self):
        """Test package not found"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {"size": 0, "records": []}

        result = task._get_package("0Ho000000000000AAA")
        assert result is None

    def test_get_package_dev_hub_error(self):
        """Test dev hub error when querying package"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        error_response = SalesforceMalformedRequest(
            "url",
            400,
            "resource_name",
            [{"message": "Object type 'Package2' is not supported"}],
        )
        task.tooling.query.side_effect = error_response

        with pytest.raises(TaskOptionsError, match="Dev Hub"):
            task._get_package("0Ho000000000000AAA")

    def test_get_package_multiple_found(self):
        """Test multiple packages with same name"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "TestPackage",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {
            "size": 2,
            "records": [
                {"Id": "0Ho000000000000AAA", "Name": "TestPackage"},
                {"Id": "0Ho000000000000BBB", "Name": "TestPackage"},
            ],
        }

        with pytest.raises(TaskOptionsError, match="Multiple packages"):
            task._get_package("TestPackage")

    def test_get_package_versions_success(self):
        """Test getting package versions"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {
            "size": 2,
            "records": [
                {
                    "Id": "05i000000000001AAA",
                    "MajorVersion": 1,
                    "MinorVersion": 0,
                    "PatchVersion": 0,
                    "IsReleased": False,
                    "IsDeprecated": False,
                    "SubscriberPackageVersionId": "04t000000000001AAA",
                },
                {
                    "Id": "05i000000000002AAA",
                    "MajorVersion": 1,
                    "MinorVersion": 1,
                    "PatchVersion": 0,
                    "IsReleased": False,
                    "IsDeprecated": False,
                    "SubscriberPackageVersionId": "04t000000000002AAA",
                },
            ],
        }

        result = task._get_package_versions("0Ho000000000000AAA")
        assert len(result) == 2
        assert result[0]["Id"] == "05i000000000001AAA"
        assert "IsDeprecated = FALSE" in task.tooling.query.call_args[0][0]

    def test_get_package_versions_empty(self):
        """Test getting package versions when none exist"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()
        task.tooling.query.return_value = {"size": 0, "records": []}

        result = task._get_package_versions("0Ho000000000000AAA")
        assert result == []

    def test_check_can_deprecate_version_unlocked(self):
        """Test can deprecate unlocked package version"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        version = {
            "Id": "05i000000000001AAA",
            "IsReleased": True,
        }
        assert task._check_can_deprecate_version(version, "Unlocked") is True

    def test_check_can_deprecate_version_managed_not_released(self):
        """Test can deprecate managed package version that is not released"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        version = {
            "Id": "05i000000000001AAA",
            "IsReleased": False,
        }
        assert task._check_can_deprecate_version(version, "Managed") is True

    def test_check_can_deprecate_version_managed_released(self):
        """Test cannot deprecate managed package version that is released"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        version = {
            "Id": "05i000000000001AAA",
            "IsReleased": True,
        }
        assert task._check_can_deprecate_version(version, "Managed") is False

    def test_check_can_deprecate_package_unlocked(self):
        """Test can deprecate unlocked package"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        package_info = {"ContainerOptions": "Unlocked"}
        versions = [{"IsReleased": True}]
        assert task._check_can_deprecate_package(package_info, versions) is True

    def test_check_can_deprecate_package_managed_no_released_versions(self):
        """Test can deprecate managed package with no released versions"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        package_info = {"ContainerOptions": "Managed"}
        versions = [{"IsReleased": False}]
        assert task._check_can_deprecate_package(package_info, versions) is True

    def test_check_can_deprecate_package_managed_with_released_versions(self):
        """Test cannot deprecate managed package with released versions"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()

        package_info = {"ContainerOptions": "Managed"}
        versions = [{"IsReleased": True}]
        assert task._check_can_deprecate_package(package_info, versions) is False

    def test_deprecate_versions_success(self):
        """Test successful deprecation of versions"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        Package2Version = mock.Mock()
        Package2Version.update.return_value = {"success": True}
        task._get_tooling_object = mock.Mock(return_value=Package2Version)

        versions = [
            {
                "Id": "05i000000000001AAA",
                "MajorVersion": 1,
                "MinorVersion": 0,
                "PatchVersion": 0,
                "SubscriberPackageVersionId": "04t000000000001AAA",
            }
        ]

        task._deprecate_versions(versions)
        Package2Version.update.assert_called_once_with(
            "05i000000000001AAA", {"IsDeprecated": True}
        )

    def test_deprecate_versions_failure(self):
        """Test failure when deprecating versions"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        Package2Version = mock.Mock()
        Package2Version.update.side_effect = Exception("Update failed")
        task._get_tooling_object = mock.Mock(return_value=Package2Version)

        versions = [
            {
                "Id": "05i000000000001AAA",
                "MajorVersion": 1,
                "MinorVersion": 0,
                "PatchVersion": 0,
                "SubscriberPackageVersionId": "04t000000000001AAA",
            }
        ]

        with pytest.raises(SalesforceException, match="Failed to delete"):
            task._deprecate_versions(versions)

    def test_deprecate_package_success(self):
        """Test successful deprecation of package"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        Package2 = mock.Mock()
        Package2.update.return_value = {"success": True}
        task._get_tooling_object = mock.Mock(return_value=Package2)

        task._deprecate_package("0Ho000000000000AAA", "TestPackage")
        Package2.update.assert_called_once_with(
            "0Ho000000000000AAA", {"IsDeprecated": True}
        )

    def test_deprecate_package_failure(self):
        """Test failure when deprecating package"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        Package2 = mock.Mock()
        Package2.update.side_effect = Exception("Update failed")
        task._get_tooling_object = mock.Mock(return_value=Package2)

        with pytest.raises(SalesforceException, match="Failed to delete Package2"):
            task._deprecate_package("0Ho000000000000AAA", "TestPackage")

    @mock.patch("cumulusci.tasks.salesforce.deprecate_package.click.confirm")
    def test_run_task_with_versions_and_confirmation(self, mock_confirm):
        """Test full task execution with versions and user confirmation"""
        mock_confirm.return_value = True
        import click

        click.no_prompt = False

        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        # Mock queries
        task.tooling.query.side_effect = [
            # Get package
            {
                "size": 1,
                "records": [
                    {
                        "Id": "0Ho000000000000AAA",
                        "Name": "TestPackage",
                        "ContainerOptions": "Unlocked",
                        "IsDeprecated": False,
                    }
                ],
            },
            # Get versions
            {
                "size": 1,
                "records": [
                    {
                        "Id": "05i000000000001AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "IsReleased": False,
                        "IsDeprecated": False,
                        "SubscriberPackageVersionId": "04t000000000001AAA",
                    }
                ],
            },
        ]

        Package2Version = mock.Mock()
        Package2Version.update.return_value = {"success": True}
        Package2 = mock.Mock()
        Package2.update.return_value = {"success": True}
        task._get_tooling_object = mock.Mock(side_effect=[Package2Version, Package2])

        task._run_task()

        # Verify versions were deprecated
        Package2Version.update.assert_called_once_with(
            "05i000000000001AAA", {"IsDeprecated": True}
        )
        # Verify package was deprecated
        Package2.update.assert_called_once_with(
            "0Ho000000000000AAA", {"IsDeprecated": True}
        )
        # Verify confirmation was requested
        mock_confirm.assert_called_once()

    @mock.patch("cumulusci.tasks.salesforce.deprecate_package.click.confirm")
    def test_run_task_user_cancels(self, mock_confirm):
        """Test user cancellation"""
        mock_confirm.return_value = False
        import click

        click.no_prompt = False

        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        task.tooling.query.side_effect = [
            {
                "size": 1,
                "records": [
                    {
                        "Id": "0Ho000000000000AAA",
                        "Name": "TestPackage",
                        "ContainerOptions": "Unlocked",
                        "IsDeprecated": False,
                    }
                ],
            },
            {
                "size": 1,
                "records": [
                    {
                        "Id": "05i000000000001AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "IsReleased": False,
                        "IsDeprecated": False,
                        "SubscriberPackageVersionId": "04t000000000001AAA",
                    }
                ],
            },
        ]

        Package2Version = mock.Mock()
        task._get_tooling_object = mock.Mock(return_value=Package2Version)

        with pytest.raises(SalesforceException, match="canceled"):
            task._run_task()

        # Should not have deprecated anything
        Package2Version.update.assert_not_called()

    @mock.patch("cumulusci.tasks.salesforce.deprecate_package.click")
    def test_run_task_no_prompt(self, mock_click):
        """Test task execution without prompt"""
        mock_click.no_prompt = True
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
                "no_prompt": True,
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        task.tooling.query.side_effect = [
            {
                "size": 1,
                "records": [
                    {
                        "Id": "0Ho000000000000AAA",
                        "Name": "TestPackage",
                        "ContainerOptions": "Unlocked",
                        "IsDeprecated": False,
                    }
                ],
            },
            {"size": 0, "records": []},  # No versions
        ]

        Package2 = mock.Mock()
        Package2.update.return_value = {"success": True}
        task._get_tooling_object = mock.Mock(return_value=Package2)

        task._run_task()

        Package2.update.assert_called_once_with(
            "0Ho000000000000AAA", {"IsDeprecated": True}
        )

    def test_run_task_package_not_found(self):
        """Test task execution when package not found"""
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        task.tooling.query.side_effect = [
            {"size": 0, "records": []},  # Package not found
        ]

        with pytest.raises(TaskOptionsError, match="not found"):
            task._run_task()

    @mock.patch("cumulusci.tasks.salesforce.deprecate_package.click")
    def test_run_task_cannot_deprecate_released_managed_version(self, mock_click):
        """Test cannot deprecate released managed package version"""
        mock_click.no_prompt = True
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
                "no_prompt": True,
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        task.tooling.query.side_effect = [
            {
                "size": 1,
                "records": [
                    {
                        "Id": "0Ho000000000000AAA",
                        "Name": "TestPackage",
                        "ContainerOptions": "Managed",
                        "IsDeprecated": False,
                    }
                ],
            },
            {
                "size": 1,
                "records": [
                    {
                        "Id": "05i000000000001AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "IsReleased": True,
                        "IsDeprecated": False,
                        "SubscriberPackageVersionId": "04t000000000001AAA",
                    }
                ],
            },
        ]

        with pytest.raises(SalesforceException, match="Cannot delete released Managed"):
            task._run_task()

    @mock.patch("cumulusci.tasks.salesforce.deprecate_package.click")
    def test_run_task_cannot_deprecate_released_managed_package(self, mock_click):
        """Test cannot deprecate managed package with released versions"""
        mock_click.no_prompt = True
        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
                "no_prompt": True,
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        task.tooling.query.side_effect = [
            {
                "size": 1,
                "records": [
                    {
                        "Id": "0Ho000000000000AAA",
                        "Name": "TestPackage",
                        "ContainerOptions": "Managed",
                        "IsDeprecated": False,
                    }
                ],
            },
            {
                "size": 1,
                "records": [
                    {
                        "Id": "05i000000000001AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "IsReleased": True,
                        "IsDeprecated": False,
                        "SubscriberPackageVersionId": "04t000000000001AAA",
                    }
                ],
            },
        ]

        Package2Version = mock.Mock()
        Package2Version.update.return_value = {"success": True}
        task._get_tooling_object = mock.Mock(return_value=Package2Version)

        # This should fail at the package level check
        with pytest.raises(SalesforceException, match="Cannot delete released Managed"):
            task._run_task()

    def test_run_task_no_versions_with_confirmation(self):
        """Test task execution with no versions but with confirmation"""
        import click

        click.no_prompt = False

        task = create_task(
            DeprecatePackage,
            {
                "package": "0Ho000000000000AAA",
            },
        )
        task._init_task()
        task.tooling = mock.Mock()

        with mock.patch(
            "cumulusci.tasks.salesforce.deprecate_package.click.confirm"
        ) as mock_confirm:
            mock_confirm.return_value = True

            task.tooling.query.side_effect = [
                {
                    "size": 1,
                    "records": [
                        {
                            "Id": "0Ho000000000000AAA",
                            "Name": "TestPackage",
                            "ContainerOptions": "Unlocked",
                            "IsDeprecated": False,
                        }
                    ],
                },
                {"size": 0, "records": []},  # No versions
            ]

            Package2 = mock.Mock()
            Package2.update.return_value = {"success": True}
            task._get_tooling_object = mock.Mock(return_value=Package2)

            task._run_task()

            Package2.update.assert_called_once_with(
                "0Ho000000000000AAA", {"IsDeprecated": True}
            )
            mock_confirm.assert_called_once()
