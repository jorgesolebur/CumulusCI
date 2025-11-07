"""Tests for list_modified_files task."""
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, PropertyMock, patch

import pytest

from cumulusci.core.config import BaseProjectConfig, TaskConfig
from cumulusci.vcs.utils.list_modified_files import ListModifiedFiles


@pytest.fixture
def project_config_with_git():
    """Create a project config with git and package settings for testing.

    This follows the pattern from cumulusci/vcs/tests/conftest.py but adds
    the specific git and package configuration needed for these tests.
    """
    from cumulusci.core.config import UniversalConfig

    universal_config = UniversalConfig()
    project_config = BaseProjectConfig(universal_config, config={"no_yaml": True})
    project_config.config["project"] = {
        "git": {"default_branch": "main"},
        "package": {"path": "force-app"},
    }
    return project_config


class TestListModifiedFiles:
    """Test cases for ListModifiedFiles task."""

    @pytest.fixture(autouse=True)
    def setup_project_config(self, project_config_with_git):
        """Auto-use fixture to set up project_config for all tests."""
        self.project_config = project_config_with_git

    def _create_task(self, options=None):
        """Helper to create a task instance."""
        if options is None:
            options = {}
        task_config = TaskConfig({"options": options})
        return ListModifiedFiles(self.project_config, task_config, org_config=None)

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    def test_no_git_repo(self, mock_subprocess):
        """Test behavior when no git repository is found."""
        task = self._create_task()
        task.project_config.get_repo = Mock(return_value=None)

        task()

        assert task.return_values == {"files": set(), "file_names": set()}
        mock_subprocess.assert_not_called()

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    def test_git_diff_fails(self, mock_subprocess):
        """Test behavior when git diff command fails."""
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return non-zero exit code
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal: ambiguous argument"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values == {"files": set(), "file_names": set()}
        mock_subprocess.assert_called_once_with(
            ["git", "diff", "--name-only", "origin/main"],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    def test_git_command_not_found(self, mock_subprocess):
        """Test behavior when git command is not found."""
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock FileNotFoundError
        mock_subprocess.side_effect = FileNotFoundError("git: command not found")

        task()

        assert task.return_values == {"files": set(), "file_names": set()}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    def test_git_diff_exception(self, mock_subprocess):
        """Test behavior when git diff raises an exception."""
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock generic exception
        mock_subprocess.side_effect = Exception("Unexpected error")

        task()

        assert task.return_values == {"files": set(), "file_names": set()}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_no_files_changed(self, mock_package_path, mock_subprocess):
        """Test behavior when no files are changed."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return empty output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values == {"files": set(), "file_names": set()}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_files_changed_not_in_package_dirs(
        self, mock_package_path, mock_subprocess
    ):
        """Test behavior when files are changed but not in package directories."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files outside package directories
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "README.md\n.gitignore\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values == {"files": set(), "file_names": set()}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_files_changed_in_package_dirs(self, mock_package_path, mock_subprocess):
        """Test behavior when files are changed in package directories."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files in package directories
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app/main/default/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["files"] == [
            "force-app/main/default/classes/MyClass.cls"
        ]
        assert task.return_values["file_names"] == set()

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_files_changed_in_src_directory(self, mock_package_path, mock_subprocess):
        """Test behavior when files are changed in src directory."""
        mock_package_path.return_value = Path("src").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files in src directory
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "src/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["files"] == ["src/classes/MyClass.cls"]
        assert task.return_values["file_names"] == set()

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_extract_file_names_with_cls_extension(
        self, mock_package_path, mock_subprocess
    ):
        """Test extracting file names with .cls extension."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return .cls files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app/main/default/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["files"] == [
            "force-app/main/default/classes/MyClass.cls"
        ]
        assert task.return_values["file_names"] == {"MyClass"}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_extract_file_names_with_dot_cls_extension(
        self, mock_package_path, mock_subprocess
    ):
        """Test extracting file names with .cls extension (with dot prefix)."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": [".cls"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return .cls files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app/main/default/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["files"] == [
            "force-app/main/default/classes/MyClass.cls"
        ]
        assert task.return_values["file_names"] == {"MyClass"}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_extract_file_names_multiple_extensions(
        self, mock_package_path, mock_subprocess
    ):
        """Test extracting file names with multiple extensions."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls", "trigger"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return multiple file types
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "force-app/main/default/classes/MyClass.cls\n"
            "force-app/main/default/triggers/MyTrigger.trigger\n"
        )
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["files"]) == 2
        assert task.return_values["file_names"] == {"MyClass", "MyTrigger"}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_extract_file_names_no_matching_extensions(
        self, mock_package_path, mock_subprocess
    ):
        """Test extracting file names when no files match the extensions."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files without matching extensions
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app/main/default/flows/MyFlow.flow-meta.xml\n"
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["files"]) == 1
        assert task.return_values["file_names"] == set()

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_default_base_ref_from_config(self, mock_package_path, mock_subprocess):
        """Test that default base_ref is taken from project config."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task()  # No base_ref specified
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        task()

        # Should use default branch from config
        mock_subprocess.assert_called_once_with(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_default_base_ref_fallback_to_main(
        self, mock_package_path, mock_subprocess
    ):
        """Test that default base_ref falls back to 'main' if not in config."""
        mock_package_path.return_value = Path("force-app").absolute()
        # Remove default_branch from config
        self.project_config.config["project"]["git"] = {}
        task = self._create_task()  # No base_ref specified
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        task()

        # Should fall back to "main"
        mock_subprocess.assert_called_once_with(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_custom_directories_option(self, mock_package_path, mock_subprocess):
        """Test behavior with custom directories option."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "directories": ["custom-dir"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files in custom directory
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "custom-dir/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["files"] == ["custom-dir/classes/MyClass.cls"]

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_filter_package_changed_files_adds_default_package_dir(
        self, mock_package_path, mock_subprocess
    ):
        """Test that default package directory is added to directories list."""
        mock_package_path.return_value = Path("custom-package").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "directories": ["force-app"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "custom-package/classes/MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        # Should include custom-package directory
        assert task.return_values["files"] == ["custom-package/classes/MyClass.cls"]

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_filter_package_changed_files_windows_paths(
        self, mock_package_path, mock_subprocess
    ):
        """Test filtering with Windows-style paths."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return Windows-style paths
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app\\main\\default\\classes\\MyClass.cls\n"
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["files"]) == 1

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_logging_with_few_files(self, mock_package_path, mock_subprocess):
        """Test logging when there are few files (<= 20)."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return 5 files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(
            [f"force-app/main/default/classes/Class{i}.cls" for i in range(5)]
        )
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["files"]) == 5

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_logging_with_many_files(self, mock_package_path, mock_subprocess):
        """Test logging when there are many files (> 20)."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return 25 files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(
            [f"force-app/main/default/classes/Class{i}.cls" for i in range(25)]
        )
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["files"]) == 25

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_logging_with_few_file_names(self, mock_package_path, mock_subprocess):
        """Test logging when there are few file names (<= 20)."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return 5 files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(
            [f"force-app/main/default/classes/Class{i}.cls" for i in range(5)]
        )
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["file_names"]) == 5

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_logging_with_many_file_names(self, mock_package_path, mock_subprocess):
        """Test logging when there are many file names (> 20)."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return 25 files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "\n".join(
            [f"force-app/main/default/classes/Class{i}.cls" for i in range(25)]
        )
        mock_subprocess.return_value = mock_result

        task()

        assert len(task.return_values["file_names"]) == 25

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_multiple_files_mixed_directories(self, mock_package_path, mock_subprocess):
        """Test filtering with multiple files in different directories."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files in different locations
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "force-app/main/default/classes/MyClass.cls\n"
            "src/classes/OtherClass.cls\n"
            "README.md\n"
            "force-app/main/default/flows/MyFlow.flow\n"
        )
        mock_subprocess.return_value = mock_result

        task()

        # Should only include files from force-app and src
        assert len(task.return_values["files"]) == 3
        assert "README.md" not in task.return_values["files"]

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_extract_file_names_with_meta_xml(self, mock_package_path, mock_subprocess):
        """Test extracting file names from .cls-meta.xml files."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task(
            {
                "base_ref": "origin/main",
                "file_extensions": ["cls-meta.xml"],
            }
        )
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return .cls-meta.xml files
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "force-app/main/default/classes/MyClass.cls-meta.xml\n"
        mock_subprocess.return_value = mock_result

        task()

        assert task.return_values["file_names"] == {"MyClass"}

    @mock.patch("cumulusci.vcs.utils.list_modified_files.subprocess.run")
    @patch.object(BaseProjectConfig, "default_package_path", new_callable=PropertyMock)
    def test_git_diff_with_whitespace(self, mock_package_path, mock_subprocess):
        """Test handling of git diff output with extra whitespace."""
        mock_package_path.return_value = Path("force-app").absolute()
        task = self._create_task({"base_ref": "origin/main"})
        task.project_config.get_repo = Mock(return_value=Mock())

        # Mock subprocess.run to return files with whitespace
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "  force-app/main/default/classes/MyClass.cls  \n"
            "\n"
            "  force-app/main/default/classes/OtherClass.cls  \n"
        )
        mock_subprocess.return_value = mock_result

        task()

        # Whitespace should be stripped
        assert len(task.return_values["files"]) == 2
        assert all("  " not in f for f in task.return_values["files"])

    def test_init_options_sets_default_base_ref(self):
        """Test that _init_options sets default base_ref from config."""
        task = self._create_task()

        # base_ref should be set from config
        assert task.parsed_options.base_ref == "main"

    def test_init_options_preserves_provided_base_ref(self):
        """Test that _init_options preserves provided base_ref."""
        task = self._create_task({"base_ref": "origin/develop"})

        # base_ref should be preserved
        assert task.parsed_options.base_ref == "origin/develop"
