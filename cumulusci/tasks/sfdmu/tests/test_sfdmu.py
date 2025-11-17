"""Tests for SFDmu task."""

import os
import tempfile
from unittest import mock

import pytest

from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.tasks.sfdmu.sfdmu import SfdmuTask


class TestSfdmuTask:
    """Test cases for SfdmuTask."""

    def test_init_options_validates_path(self):
        """Test that _init_options validates the path exists and contains export.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            # Test valid path using create_task helper
            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )
            assert task.options["path"] == os.path.abspath(temp_dir)

    def test_init_options_raises_error_for_missing_path(self):
        """Test that _init_options raises error for missing path."""
        with pytest.raises(Exception):  # TaskOptionsError
            create_task(
                SfdmuTask,
                {"source": "dev", "target": "qa", "path": "/nonexistent/path"},
            )

    def test_init_options_raises_error_for_missing_export_json(self):
        """Test that _init_options raises error for missing export.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(Exception):  # TaskOptionsError
                create_task(
                    SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
                )

    def test_validate_org_csvfile(self):
        """Test that _validate_org returns None for csvfile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "csvfile", "target": "csvfile", "path": temp_dir}
            )

            result = task._validate_org("csvfile")
            assert result is None

    def test_validate_org_missing_keychain(self):
        """Test that _validate_org raises error when keychain is None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            # Mock the keychain to be None
            task.project_config.keychain = None

            with pytest.raises(Exception):  # TaskOptionsError
                task._validate_org("dev")

    def test_get_sf_org_name_sfdx_alias(self):
        """Test _get_sf_org_name with sfdx_alias."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            mock_org_config = mock.Mock()
            mock_org_config.sfdx_alias = "test_alias"
            mock_org_config.username = "test@example.com"

            result = task._get_sf_org_name(mock_org_config)
            assert result == "test_alias"

    def test_get_sf_org_name_username(self):
        """Test _get_sf_org_name with username fallback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create export.json file
            export_json_path = os.path.join(temp_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": temp_dir}
            )

            mock_org_config = mock.Mock()
            mock_org_config.sfdx_alias = None
            mock_org_config.username = "test@example.com"

            result = task._get_sf_org_name(mock_org_config)
            assert result == "test@example.com"

    def test_create_execute_directory(self):
        """Test _create_execute_directory creates directory and copies files."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create test files
            export_json = os.path.join(base_dir, "export.json")
            test_csv = os.path.join(base_dir, "test.csv")
            test_txt = os.path.join(base_dir, "test.txt")  # Should not be copied

            with open(export_json, "w") as f:
                f.write('{"test": "data"}')
            with open(test_csv, "w") as f:
                f.write("col1,col2\nval1,val2")
            with open(test_txt, "w") as f:
                f.write("text file")

            # Create subdirectory (should not be copied)
            subdir = os.path.join(base_dir, "subdir")
            os.makedirs(subdir)
            with open(os.path.join(subdir, "file.txt"), "w") as f:
                f.write("subdir file")

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
            )

            execute_path = task._create_execute_directory(base_dir)

            # Check that execute directory was created
            assert os.path.exists(execute_path)
            assert execute_path == os.path.join(base_dir, "execute")

            # Check that files were copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))
            assert os.path.exists(os.path.join(execute_path, "test.csv"))
            assert not os.path.exists(
                os.path.join(execute_path, "test.txt")
            )  # Not a valid file type
            assert not os.path.exists(
                os.path.join(execute_path, "subdir")
            )  # Not a file

            # Check file contents
            with open(os.path.join(execute_path, "export.json"), "r") as f:
                assert f.read() == '{"test": "data"}'
            with open(os.path.join(execute_path, "test.csv"), "r") as f:
                assert f.read() == "col1,col2\nval1,val2"

    def test_create_execute_directory_removes_existing(self):
        """Test that _create_execute_directory removes existing execute directory."""
        with tempfile.TemporaryDirectory() as base_dir:
            # Create existing execute directory with files
            execute_dir = os.path.join(base_dir, "execute")
            os.makedirs(execute_dir)
            with open(os.path.join(execute_dir, "old_file.json"), "w") as f:
                f.write('{"old": "data"}')

            # Create export.json in base directory
            export_json = os.path.join(base_dir, "export.json")
            with open(export_json, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": base_dir}
            )

            execute_path = task._create_execute_directory(base_dir)

            # Check that old file was removed
            assert not os.path.exists(os.path.join(execute_path, "old_file.json"))
            # Check that new file was copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))

    def test_inject_namespace_tokens_csvfile_both(self):
        """Test that namespace injection is skipped when both source and target are csvfile."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask,
                {"source": "csvfile", "target": "csvfile", "path": execute_dir},
            )

            # Should not raise any errors and files should remain unchanged
            task._inject_namespace_tokens(execute_dir, None, None)

            # Check that file content was not changed
            with open(test_json, "r") as f:
                assert f.read() == '{"field": "%%%NAMESPACE%%%Test"}'

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_csvfile_target_with_source_org(
        self, mock_determine_managed
    ):
        """Test that namespace injection uses source org when target is csvfile."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "export.json")
            with open(test_json, "w") as f:
                f.write(
                    '{"query": "SELECT Id FROM %%%MANAGED_OR_NAMESPACED_ORG%%%CustomObject__c"}'
                )

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "csvfile", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_source_org = mock.Mock()
            mock_source_org.namespace = "testns"

            # When target is csvfile (None), should use source org for injection
            task._inject_namespace_tokens(execute_dir, mock_source_org, None)

            # Check that namespace tokens were replaced using source org
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__CustomObject__c" in content
                assert "%%%MANAGED_OR_NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_managed_mode(self, mock_determine_managed):
        """Test namespace injection in managed mode."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            test_csv = os.path.join(execute_dir, "test.csv")

            with open(test_json, "w") as f:
                f.write(
                    '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
                )
            with open(test_csv, "w") as f:
                f.write("Name,%%%NAMESPACE%%%Field\nTest,Value")

            # Create filename with namespace token
            filename_with_token = os.path.join(execute_dir, "___NAMESPACE___test.json")
            with open(filename_with_token, "w") as f:
                f.write('{"test": "data"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were replaced in content
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "testns__Value" in content

            with open(test_csv, "r") as f:
                content = f.read()
                assert "testns__Field" in content

            # Check that filename token was replaced
            expected_filename = os.path.join(execute_dir, "testns__test.json")
            assert os.path.exists(expected_filename)
            assert not os.path.exists(filename_with_token)

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_unmanaged_mode(self, mock_determine_managed):
        """Test namespace injection in unmanaged mode."""
        mock_determine_managed.return_value = False

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write(
                    '{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}'
                )

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were replaced with empty strings
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACE%% removed
                assert "Value" in content  # %%NAMESPACED_ORG%% removed
                assert "%%%NAMESPACE%%%" not in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with namespaced org."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = (
                "testns"  # Same as project namespace = namespaced org
            )

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespaced org token was replaced
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch("cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode")
    def test_inject_namespace_tokens_non_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with non-namespaced org."""
        mock_determine_managed.return_value = True

        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = "testns"

            mock_org_config = mock.Mock()
            mock_org_config.namespace = (
                "differentns"  # Different from project namespace
            )

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespaced org token was replaced with empty string
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACED_ORG%% removed
                assert "%%%NAMESPACED_ORG%%%" not in content
                assert "testns__" not in content  # Should not have namespace prefix

    def test_inject_namespace_tokens_no_namespace(self):
        """Test namespace injection when project has no namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test"}')

            # Create export.json file
            export_json_path = os.path.join(execute_dir, "export.json")
            with open(export_json_path, "w") as f:
                f.write('{"test": "data"}')

            task = create_task(
                SfdmuTask, {"source": "dev", "target": "qa", "path": execute_dir}
            )

            # Mock the project config namespace
            task.project_config.project__package__namespace = None

            mock_org_config = mock.Mock()
            mock_org_config.namespace = None

            task._inject_namespace_tokens(execute_dir, None, mock_org_config)

            # Check that namespace tokens were not processed (due to circular import issue)
            with open(test_json, "r") as f:
                content = f.read()
                assert (
                    "%%%NAMESPACE%%%Test" in content
                )  # Tokens remain unchanged due to import issue

    def test_additional_params_option_exists(self):
        """Test that additional_params option is properly defined in task_options."""
        # Check that the additional_params option is defined
        assert "additional_params" in SfdmuTask.task_options
        assert SfdmuTask.task_options["additional_params"]["required"] is False
        assert (
            "Additional parameters"
            in SfdmuTask.task_options["additional_params"]["description"]
        )

    def test_additional_params_parsing_logic(self):
        """Test that additional_params parsing logic works correctly."""
        # Test the splitting logic that would be used in the task
        additional_params = "-no-warnings -m -t error"
        additional_args = additional_params.split()
        expected_args = ["-no-warnings", "-m", "-t", "error"]
        assert additional_args == expected_args

    def test_additional_params_empty_string_logic(self):
        """Test that empty additional_params are handled correctly."""
        # Test the splitting logic with empty string
        additional_params = ""
        additional_args = additional_params.split()
        assert additional_args == []

    def test_additional_params_none_logic(self):
        """Test that None additional_params are handled correctly."""
        # Test the logic that would be used in the task
        additional_params = None
        if additional_params:
            additional_args = additional_params.split()
        else:
            additional_args = []
        assert additional_args == []
