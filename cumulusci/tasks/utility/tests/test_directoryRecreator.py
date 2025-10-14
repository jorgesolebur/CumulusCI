"""Tests for directoryRecreator module."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from cumulusci.core.config import TaskConfig
from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.utility.directoryRecreator import DirectoryRecreator


class TestDirectoryRecreatorOptions:
    """Test cases for DirectoryRecreator options configuration."""

    def test_required_path_option(self):
        """Test that path option is required."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_directory")
            task_config = TaskConfig({"options": {"path": test_dir}})

            task = DirectoryRecreator(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert task.parsed_options.path == Path(test_dir)

    def test_path_as_string(self):
        """Test initialization with path as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_dir")
            task_config = TaskConfig({"options": {"path": test_dir}})

            task = DirectoryRecreator(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert isinstance(task.parsed_options.path, Path)
            assert str(task.parsed_options.path) == test_dir

    def test_path_as_path_object(self):
        """Test initialization with path as Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_dir"
            task_config = TaskConfig({"options": {"path": test_dir}})

            task = DirectoryRecreator(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert task.parsed_options.path == test_dir


class TestDirectoryRecreatorInitialization:
    """Test cases for DirectoryRecreator initialization methods."""

    def test_init_options_raises_error_when_path_is_file(self):
        """Test that _init_options raises TaskOptionsError when path is a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file, not a directory
            test_file = os.path.join(tmpdir, "test_file.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            task_config = TaskConfig({"options": {"path": test_file}})

            with pytest.raises(TaskOptionsError) as exc_info:
                DirectoryRecreator(
                    project_config=mock.Mock(),
                    task_config=task_config,
                    org_config=None,
                )

            assert f"Path {test_file} is a file" in str(exc_info.value)

    def test_init_options_succeeds_when_path_is_directory(self):
        """Test that _init_options succeeds when path is an existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_directory")
            os.makedirs(test_dir)

            task_config = TaskConfig({"options": {"path": test_dir}})

            task = DirectoryRecreator(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert task.parsed_options.path == Path(test_dir)

    def test_init_options_succeeds_when_path_does_not_exist(self):
        """Test that _init_options succeeds when path doesn't exist yet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "non_existent_directory")

            task_config = TaskConfig({"options": {"path": test_dir}})

            task = DirectoryRecreator(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert task.parsed_options.path == Path(test_dir)


class TestDirectoryRecreatorRunTask:
    """Test cases for _run_task method."""

    def test_run_task_creates_new_directory(self):
        """Test _run_task creates a new directory when path doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "new_directory")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Directory should not exist yet
            assert not os.path.exists(test_dir)

            # Run the task
            task()

            # Directory should now exist
            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)

    def test_run_task_recreates_existing_directory(self):
        """Test _run_task removes and recreates an existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "existing_directory")

            # Create directory with a file inside
            os.makedirs(test_dir)
            test_file = os.path.join(test_dir, "test_file.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            # Verify directory and file exist
            assert os.path.exists(test_dir)
            assert os.path.exists(test_file)

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Run the task
            task()

            # Directory should exist but file should be gone
            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)
            assert not os.path.exists(test_file)

    def test_run_task_logs_created_message_for_new_directory(self):
        """Test _run_task logs 'created' message for new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "new_directory")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            with mock.patch.object(task.logger, "info") as mock_logger:
                task()

                # Check that the correct message was logged (may be called multiple times by BaseTask)
                log_messages = [call[0][0] for call in mock_logger.call_args_list]
                assert any(
                    "created" in msg
                    and "removed and created" not in msg
                    and str(test_dir) in msg
                    for msg in log_messages
                )

    def test_run_task_logs_removed_and_created_message_for_existing_directory(self):
        """Test _run_task logs 'removed and created' message for existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "existing_directory")
            os.makedirs(test_dir)

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            with mock.patch.object(task.logger, "info") as mock_logger:
                task()

                # Check that the correct message was logged (may be called multiple times by BaseTask)
                log_messages = [call[0][0] for call in mock_logger.call_args_list]
                assert any(
                    "removed and created" in msg and str(test_dir) in msg
                    for msg in log_messages
                )

    def test_run_task_handles_nested_directory_path(self):
        """Test _run_task can create nested directory paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "parent", "child", "grandchild")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Run the task
            task()

            # All nested directories should exist
            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)

    def test_run_task_preserves_parent_directories(self):
        """Test _run_task only removes the specified directory, not parents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent_dir = os.path.join(tmpdir, "parent")
            child_dir = os.path.join(parent_dir, "child")

            # Create parent and child directories
            os.makedirs(child_dir)

            # Create files in both directories
            parent_file = os.path.join(parent_dir, "parent.txt")
            child_file = os.path.join(child_dir, "child.txt")

            with open(parent_file, "w") as f:
                f.write("parent content")
            with open(child_file, "w") as f:
                f.write("child content")

            task_config = TaskConfig({"options": {"path": child_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Run the task
            task()

            # Parent directory and its file should still exist
            assert os.path.exists(parent_dir)
            assert os.path.exists(parent_file)

            # Child directory should exist but its file should be gone
            assert os.path.exists(child_dir)
            assert not os.path.exists(child_file)

    def test_run_task_with_relative_path(self):
        """Test _run_task works with relative paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                test_dir = "relative_test_dir"

                task_config = TaskConfig({"options": {"path": test_dir}})

                project_config = mock.Mock()
                project_config.repo_root = tmpdir

                task = DirectoryRecreator(
                    project_config=project_config,
                    task_config=task_config,
                    org_config=None,
                )

                # Run the task
                task()

                # Directory should exist
                assert os.path.exists(test_dir)
                assert os.path.isdir(test_dir)
            finally:
                os.chdir(original_cwd)

    def test_run_task_with_directory_containing_subdirectories(self):
        """Test _run_task removes directory with complex structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "complex_directory")

            # Create complex directory structure
            os.makedirs(os.path.join(test_dir, "subdir1", "subdir2"))
            os.makedirs(os.path.join(test_dir, "subdir3"))

            # Create files in various locations
            with open(os.path.join(test_dir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(test_dir, "subdir1", "file2.txt"), "w") as f:
                f.write("content2")
            with open(
                os.path.join(test_dir, "subdir1", "subdir2", "file3.txt"), "w"
            ) as f:
                f.write("content3")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Run the task
            task()

            # Directory should exist but be empty
            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)
            assert len(os.listdir(test_dir)) == 0


class TestDirectoryRecreatorEdgeCases:
    """Test cases for edge cases and special scenarios."""

    def test_task_with_path_containing_spaces(self):
        """Test task handles paths with spaces correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "directory with spaces")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            task()

            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)

    def test_task_with_path_containing_special_characters(self):
        """Test task handles paths with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test-dir_123")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            task()

            assert os.path.exists(test_dir)
            assert os.path.isdir(test_dir)

    def test_task_called_multiple_times(self):
        """Test task can be called multiple times successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_directory")

            task_config = TaskConfig({"options": {"path": test_dir}})

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = DirectoryRecreator(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # Run the task multiple times
            task()
            assert os.path.exists(test_dir)

            # Add a file
            with open(os.path.join(test_dir, "file.txt"), "w") as f:
                f.write("content")

            task()
            assert os.path.exists(test_dir)
            assert len(os.listdir(test_dir)) == 0

            task()
            assert os.path.exists(test_dir)
            assert len(os.listdir(test_dir)) == 0
