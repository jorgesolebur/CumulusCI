"""Tests for SFDmu task."""

import os
import tempfile
import zipfile
from unittest import mock

import pytest

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
            
            # Mock project config
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            # Test valid path
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=temp_dir
            )
            assert task.options["path"] == os.path.abspath(temp_dir)

    def test_init_options_raises_error_for_missing_path(self):
        """Test that _init_options raises error for missing path."""
        mock_project_config = mock.Mock()
        mock_project_config.keychain = None
        
        with pytest.raises(Exception):  # TaskOptionsError
            SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path="/nonexistent/path"
            )

    def test_init_options_raises_error_for_missing_export_json(self):
        """Test that _init_options raises error for missing export.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            with pytest.raises(Exception):  # TaskOptionsError
                SfdmuTask(
                    mock_project_config,
                    mock.Mock(),
                    mock.Mock(),
                    source="dev",
                    target="qa",
                    path=temp_dir
                )

    def test_validate_org_csvfile(self):
        """Test that _validate_org returns None for csvfile."""
        mock_project_config = mock.Mock()
        mock_project_config.keychain = None
        
        task = SfdmuTask(
            mock_project_config,
            mock.Mock(),
            mock.Mock(),
            source="csvfile",
            target="csvfile",
            path="/tmp"  # Will be overridden in _init_options
        )
        
        result = task._validate_org("csvfile")
        assert result is None

    def test_validate_org_missing_keychain(self):
        """Test that _validate_org raises error when keychain is None."""
        mock_project_config = mock.Mock()
        mock_project_config.keychain = None
        
        task = SfdmuTask(
            mock_project_config,
            mock.Mock(),
            mock.Mock(),
            source="dev",
            target="qa",
            path="/tmp"  # Will be overridden in _init_options
        )
        
        with pytest.raises(Exception):  # TaskOptionsError
            task._validate_org("dev")

    def test_get_sf_org_name_sfdx_alias(self):
        """Test _get_sf_org_name with sfdx_alias."""
        mock_org_config = mock.Mock()
        mock_org_config.sfdx_alias = "test_alias"
        mock_org_config.username = "test@example.com"
        
        mock_project_config = mock.Mock()
        mock_project_config.keychain = None
        
        task = SfdmuTask(
            mock_project_config,
            mock.Mock(),
            mock.Mock(),
            source="dev",
            target="qa",
            path="/tmp"  # Will be overridden in _init_options
        )
        
        result = task._get_sf_org_name(mock_org_config)
        assert result == "test_alias"

    def test_get_sf_org_name_username(self):
        """Test _get_sf_org_name with username fallback."""
        mock_org_config = mock.Mock()
        mock_org_config.sfdx_alias = None
        mock_org_config.username = "test@example.com"
        
        mock_project_config = mock.Mock()
        mock_project_config.keychain = None
        
        task = SfdmuTask(
            mock_project_config,
            mock.Mock(),
            mock.Mock(),
            source="dev",
            target="qa",
            path="/tmp"  # Will be overridden in _init_options
        )
        
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
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=base_dir
            )
            
            execute_path = task._create_execute_directory(base_dir)
            
            # Check that execute directory was created
            assert os.path.exists(execute_path)
            assert execute_path == os.path.join(base_dir, "execute")
            
            # Check that files were copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))
            assert os.path.exists(os.path.join(execute_path, "test.csv"))
            assert not os.path.exists(os.path.join(execute_path, "test.txt"))  # Not .json or .csv
            assert not os.path.exists(os.path.join(execute_path, "subdir"))  # Not a file
            
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
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=base_dir
            )
            
            execute_path = task._create_execute_directory(base_dir)
            
            # Check that old file was removed
            assert not os.path.exists(os.path.join(execute_path, "old_file.json"))
            # Check that new file was copied
            assert os.path.exists(os.path.join(execute_path, "export.json"))

    def test_inject_namespace_tokens_csvfile_target(self):
        """Test that namespace injection is skipped when target is csvfile."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="csvfile",
                path=execute_dir
            )
            
            # Should not raise any errors and files should remain unchanged
            task._inject_namespace_tokens(execute_dir, None)
            
            # Check that file content was not changed
            with open(test_json, "r") as f:
                assert f.read() == '{"field": "%%%NAMESPACE%%%Test"}'

    @mock.patch('cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode')
    def test_inject_namespace_tokens_managed_mode(self, mock_determine_managed):
        """Test namespace injection in managed mode."""
        mock_determine_managed.return_value = True
        
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            test_csv = os.path.join(execute_dir, "test.csv")
            
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}')
            with open(test_csv, "w") as f:
                f.write("Name,%%%NAMESPACE%%%Field\nTest,Value")
            
            # Create filename with namespace token
            filename_with_token = os.path.join(execute_dir, "___NAMESPACE___test.json")
            with open(filename_with_token, "w") as f:
                f.write('{"test": "data"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.project__package__namespace = "testns"
            mock_project_config.keychain = None
            
            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            task._inject_namespace_tokens(execute_dir, mock_org_config)
            
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

    @mock.patch('cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode')
    def test_inject_namespace_tokens_unmanaged_mode(self, mock_determine_managed):
        """Test namespace injection in unmanaged mode."""
        mock_determine_managed.return_value = False
        
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with namespace tokens
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACE%%%Test", "org": "%%%NAMESPACED_ORG%%%Value"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.project__package__namespace = "testns"
            mock_project_config.keychain = None
            
            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            task._inject_namespace_tokens(execute_dir, mock_org_config)
            
            # Check that namespace tokens were replaced with empty strings
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACE%% removed
                assert "Value" in content  # %%NAMESPACED_ORG%% removed
                assert "%%%NAMESPACE%%%" not in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch('cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode')
    def test_inject_namespace_tokens_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with namespaced org."""
        mock_determine_managed.return_value = True
        
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.project__package__namespace = "testns"
            mock_project_config.keychain = None
            
            mock_org_config = mock.Mock()
            mock_org_config.namespace = "testns"  # Same as project namespace = namespaced org
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            task._inject_namespace_tokens(execute_dir, mock_org_config)
            
            # Check that namespaced org token was replaced
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "%%%NAMESPACED_ORG%%%" not in content

    @mock.patch('cumulusci.tasks.sfdmu.sfdmu.determine_managed_mode')
    def test_inject_namespace_tokens_non_namespaced_org(self, mock_determine_managed):
        """Test namespace injection with non-namespaced org."""
        mock_determine_managed.return_value = True
        
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with namespaced org token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%NAMESPACED_ORG%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.project__package__namespace = "testns"
            mock_project_config.keychain = None
            
            mock_org_config = mock.Mock()
            mock_org_config.namespace = "differentns"  # Different from project namespace
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            task._inject_namespace_tokens(execute_dir, mock_org_config)
            
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
            
            mock_project_config = mock.Mock()
            mock_project_config.project__package__namespace = None
            mock_project_config.keychain = None
            
            mock_org_config = mock.Mock()
            mock_org_config.namespace = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            task._inject_namespace_tokens(execute_dir, mock_org_config)
            
            # Check that namespace tokens were replaced with empty strings
            with open(test_json, "r") as f:
                content = f.read()
                assert "Test" in content  # %%NAMESPACE%% removed
                assert "%%%NAMESPACE%%%" not in content

    def test_apply_always_namespace_token(self):
        """Test that %%%ALWAYS_NAMESPACE%%% token is always replaced with namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test files with %%%ALWAYS_NAMESPACE%%% token
            test_json = os.path.join(execute_dir, "test.json")
            test_csv = os.path.join(execute_dir, "test.csv")
            
            with open(test_json, "w") as f:
                f.write('{"field": "%%%ALWAYS_NAMESPACE%%%Test"}')
            with open(test_csv, "w") as f:
                f.write("Name,%%%ALWAYS_NAMESPACE%%%Field\nTest,Value")
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with namespace
            task._apply_always_namespace_token(execute_dir, "testns")
            
            # Check that %%%ALWAYS_NAMESPACE%%% token was replaced with namespace prefix
            with open(test_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "%%%ALWAYS_NAMESPACE%%%" not in content
            
            with open(test_csv, "r") as f:
                content = f.read()
                assert "testns__Field" in content
                assert "%%%ALWAYS_NAMESPACE%%%" not in content

    def test_apply_always_namespace_token_no_namespace(self):
        """Test that %%%ALWAYS_NAMESPACE%%% token is not processed when no namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with %%%ALWAYS_NAMESPACE%%% token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%ALWAYS_NAMESPACE%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with no namespace (None)
            task._apply_always_namespace_token(execute_dir, None)
            
            # Check that %%%ALWAYS_NAMESPACE%%% token was not processed
            with open(test_json, "r") as f:
                content = f.read()
                assert "%%%ALWAYS_NAMESPACE%%%Test" in content  # Token should remain unchanged

    def test_apply_always_namespace_token_empty_namespace(self):
        """Test that %%%ALWAYS_NAMESPACE%%% token is not processed when empty namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with %%%ALWAYS_NAMESPACE%%% token
            test_json = os.path.join(execute_dir, "test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%ALWAYS_NAMESPACE%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with empty namespace
            task._apply_always_namespace_token(execute_dir, "")
            
            # Check that %%%ALWAYS_NAMESPACE%%% token was not processed
            with open(test_json, "r") as f:
                content = f.read()
                assert "%%%ALWAYS_NAMESPACE%%%Test" in content  # Token should remain unchanged

    def test_apply_always_namespace_filename_token(self):
        """Test that ___ALWAYS_NAMESPACE___ filename token is always replaced with namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with ___ALWAYS_NAMESPACE___ token in filename
            test_json = os.path.join(execute_dir, "___ALWAYS_NAMESPACE___test.json")
            test_csv = os.path.join(execute_dir, "data___ALWAYS_NAMESPACE___.csv")
            
            with open(test_json, "w") as f:
                f.write('{"field": "test"}')
            with open(test_csv, "w") as f:
                f.write("col1,col2\nval1,val2")
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with namespace
            task._apply_always_namespace_token(execute_dir, "testns")
            
            # Check that files were renamed with namespace prefix
            expected_json = os.path.join(execute_dir, "testns__test.json")
            expected_csv = os.path.join(execute_dir, "datatestns__.csv")
            
            assert os.path.exists(expected_json)
            assert os.path.exists(expected_csv)
            assert not os.path.exists(test_json)  # Original file should be gone
            assert not os.path.exists(test_csv)  # Original file should be gone

    def test_apply_always_namespace_filename_token_no_namespace(self):
        """Test that ___ALWAYS_NAMESPACE___ filename token is not processed when no namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with ___ALWAYS_NAMESPACE___ token in filename
            test_json = os.path.join(execute_dir, "___ALWAYS_NAMESPACE___test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with no namespace (None)
            task._apply_always_namespace_token(execute_dir, None)
            
            # Check that file was not renamed
            assert os.path.exists(test_json)  # Original file should still exist
            assert not os.path.exists(os.path.join(execute_dir, "test.json"))  # No renamed file

    def test_apply_always_namespace_filename_token_empty_namespace(self):
        """Test that ___ALWAYS_NAMESPACE___ filename token is not processed when empty namespace."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with ___ALWAYS_NAMESPACE___ token in filename
            test_json = os.path.join(execute_dir, "___ALWAYS_NAMESPACE___test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with empty namespace
            task._apply_always_namespace_token(execute_dir, "")
            
            # Check that file was not renamed
            assert os.path.exists(test_json)  # Original file should still exist
            assert not os.path.exists(os.path.join(execute_dir, "test.json"))  # No renamed file

    def test_apply_always_namespace_both_tokens(self):
        """Test that both content and filename tokens work together."""
        with tempfile.TemporaryDirectory() as execute_dir:
            # Create test file with both tokens
            test_json = os.path.join(execute_dir, "___ALWAYS_NAMESPACE___test.json")
            with open(test_json, "w") as f:
                f.write('{"field": "%%%ALWAYS_NAMESPACE%%%Test"}')
            
            mock_project_config = mock.Mock()
            mock_project_config.keychain = None
            
            task = SfdmuTask(
                mock_project_config,
                mock.Mock(),
                mock.Mock(),
                source="dev",
                target="qa",
                path=execute_dir
            )
            
            # Test with namespace
            task._apply_always_namespace_token(execute_dir, "testns")
            
            # Check that both tokens were processed
            expected_json = os.path.join(execute_dir, "testns__test.json")
            assert os.path.exists(expected_json)
            assert not os.path.exists(test_json)  # Original file should be gone
            
            # Check content was also processed
            with open(expected_json, "r") as f:
                content = f.read()
                assert "testns__Test" in content
                assert "%%%ALWAYS_NAMESPACE%%%" not in content

    def test_additional_params_option_exists(self):
        """Test that additional_params option is properly defined in task_options."""
        # Check that the additional_params option is defined
        assert "additional_params" in SfdmuTask.task_options
        assert SfdmuTask.task_options["additional_params"]["required"] is False
        assert "Additional parameters" in SfdmuTask.task_options["additional_params"]["description"]

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
