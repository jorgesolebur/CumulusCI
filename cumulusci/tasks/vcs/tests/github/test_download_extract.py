import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from cumulusci.core.config import TaskConfig
from cumulusci.core.exceptions import CumulusCIException, TaskOptionsError
from cumulusci.tasks.vcs.download_extract import TRACKING_FILE_NAME, DownloadExtract
from cumulusci.tests.util import create_project_config


class TestDownloadExtract:
    def setup_method(self):
        self.project_config = create_project_config("TestRepo", "TestOwner")
        self.repo_url = "https://github.com/TestOwner/TestRepo.git"

    def test_init_options__default(self):
        """Test initialization with default options"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.repo_url == self.repo_url
        assert task.parsed_options.target_directory == "test_dir"
        assert task.parsed_options.include is None
        assert task.parsed_options.renames == {}
        assert task.parsed_options.force is False

    def test_init_options__with_include_list(self):
        """Test initialization with include list"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "include": ["src/", "docs/README.md"],
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.include == ["src/", "docs/README.md"]

    def test_init_options__with_include_string(self):
        """Test initialization with include as string"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "include": "src/,docs/README.md",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.include == ["src/", "docs/README.md"]

    def test_init_options__with_force_true(self):
        """Test initialization with force option as True"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "force": True,
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.force is True

    def test_init_options__with_force_string(self):
        """Test initialization with force option as string"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "force": "true",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.force is True

    def test_process_renames__valid_renames(self):
        """Test processing valid renames"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": [
                        {"local": "src/old.py", "target": "src/new.py"},
                        {"local": "docs/", "target": "documentation/"},
                    ],
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        expected_renames = {
            "src/old.py": "src/new.py",
            "docs/": "documentation/",
        }
        assert task.parsed_options.renames == expected_renames

    def test_process_renames__empty_renames(self):
        """Test processing empty renames"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": [],
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.renames == {}

    def test_process_renames__none_renames(self):
        """Test processing None renames"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        assert task.parsed_options.renames == {}

    def test_process_renames__invalid_not_list_of_dicts(self):
        """Test processing invalid renames - not list of dicts"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": ["src/old.py", "src/new.py"],
                }
            }
        )

        with pytest.raises(TaskOptionsError) as exc:
            DownloadExtract(self.project_config, task_config)

        assert (
            "Renamed paths must be a list of dicts with `local:` and `target:` keys."
            in str(exc.value)
        )

    def test_process_renames__invalid_wrong_keys(self):
        """Test processing invalid renames - wrong keys"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": [
                        {"source": "src/old.py", "destination": "src/new.py"},
                    ],
                }
            }
        )

        with pytest.raises(TaskOptionsError) as exc:
            DownloadExtract(self.project_config, task_config)

        assert (
            "Renamed paths must be a list of dicts with `local:` and `target:` keys."
            in str(exc.value)
        )

    def test_process_renames__invalid_empty_values(self):
        """Test processing invalid renames - empty values"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": [
                        {"local": "src/old.py", "target": ""},
                    ],
                }
            }
        )

        with pytest.raises(TaskOptionsError) as exc:
            DownloadExtract(self.project_config, task_config)

        assert (
            "Renamed paths must be a list of dicts with `local:` and `target:` keys."
            in str(exc.value)
        )

    def test_process_renames__invalid_none_values(self):
        """Test processing invalid renames - None values"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "renames": [
                        {"local": None, "target": "src/new.py"},
                    ],
                }
            }
        )

        with pytest.raises(TaskOptionsError) as exc:
            DownloadExtract(self.project_config, task_config)

        assert (
            "Renamed paths must be a list of dicts with `local:` and `target:` keys."
            in str(exc.value)
        )

    @mock.patch("cumulusci.tasks.vcs.download_extract.get_repo_from_url")
    def test_set_ref__with_branch(self, mock_get_repo):
        """Test _set_ref with branch option"""
        mock_repo = mock.Mock()
        mock_get_repo.return_value = mock_repo

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "branch": "main",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock_repo

        task._set_ref()

        assert task.ref == "heads/main"

    @mock.patch("cumulusci.tasks.vcs.download_extract.get_repo_from_url")
    @mock.patch("cumulusci.tasks.vcs.download_extract.get_ref_from_options")
    def test_set_ref__with_tag_name(self, mock_get_ref, mock_get_repo):
        """Test _set_ref with tag_name option"""
        mock_repo = mock.Mock()
        mock_get_repo.return_value = mock_repo
        mock_get_ref.return_value = "tags/v1.0.0"

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "tag_name": "v1.0.0",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock_repo

        task._set_ref()

        assert task.ref == "tags/v1.0.0"
        mock_get_ref.assert_called_once_with(task.project_config, task.parsed_options)

    @mock.patch("cumulusci.tasks.vcs.download_extract.get_repo_from_url")
    @mock.patch("cumulusci.tasks.vcs.download_extract.get_ref_from_options")
    def test_set_ref__with_ref(self, mock_get_ref, mock_get_repo):
        """Test _set_ref with ref option"""
        mock_repo = mock.Mock()
        mock_get_repo.return_value = mock_repo
        mock_get_ref.return_value = "refs/heads/feature-branch"

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "ref": "feature-branch",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock_repo

        task._set_ref()

        assert task.ref == "refs/heads/feature-branch"
        mock_get_ref.assert_called_once_with(task.project_config, task.parsed_options)

    @mock.patch("cumulusci.tasks.vcs.download_extract.get_repo_from_url")
    @mock.patch("cumulusci.tasks.vcs.download_extract.get_ref_from_options")
    def test_set_ref__fallback_to_default_branch(self, mock_get_ref, mock_get_repo):
        """Test _set_ref fallback to default branch"""
        mock_repo = mock.Mock()
        mock_repo.default_branch = "main"
        mock_get_repo.return_value = mock_repo
        mock_get_ref.side_effect = CumulusCIException("No ref found")

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock_repo

        task._set_ref()

        assert task.ref == "heads/main"

    @mock.patch("cumulusci.tasks.vcs.download_extract.get_repo_from_url")
    def test_init_repo(self, mock_get_repo):
        """Test _init_repo method"""
        mock_repo = mock.Mock()
        mock_ref = mock.Mock()
        mock_ref.sha = "abc123"
        mock_repo.get_ref.return_value = mock_ref
        mock_get_repo.return_value = mock_repo

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "branch": "main",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        task._init_repo()

        assert task.repo == mock_repo
        assert task.ref == "heads/main"
        assert task.commit == "abc123"
        mock_get_repo.assert_called_once_with(task.project_config, self.repo_url)

    def test_set_target_directory__relative_path(self):
        """Test _set_target_directory with relative path"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        task._set_target_directory()

        expected_path = os.path.join(self.project_config.repo_root, "test_dir")
        assert task.parsed_options.target_directory == expected_path

    def test_set_target_directory__absolute_path(self):
        """Test _set_target_directory with absolute path"""
        absolute_path = tempfile.mkdtemp(prefix="test_")
        try:
            task_config = TaskConfig(
                {
                    "options": {
                        "repo_url": self.repo_url,
                        "target_directory": absolute_path,
                    }
                }
            )
            task = DownloadExtract(self.project_config, task_config)

            task._set_target_directory()

            assert task.parsed_options.target_directory == absolute_path
        finally:
            # Clean up the temporary directory
            os.rmdir(absolute_path)

    def test_rename_files(self):
        """Test _rename_files method"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file = Path(temp_dir) / "old_file.txt"
            test_file.write_text("test content")

            test_dir = Path(temp_dir) / "old_dir"
            test_dir.mkdir()
            (test_dir / "file.txt").write_text("content")

            # Setup task
            task_config = TaskConfig(
                {
                    "options": {
                        "repo_url": self.repo_url,
                        "target_directory": temp_dir,
                        "renames": [
                            {"local": "old_file.txt", "target": "new_file.txt"},
                            {"local": "old_dir", "target": "new_dir"},
                        ],
                    }
                }
            )
            task = DownloadExtract(self.project_config, task_config)

            # Run rename
            task._rename_files(temp_dir)

            # Check results
            assert not test_file.exists()
            assert not test_dir.exists()
            assert (Path(temp_dir) / "new_file.txt").exists()
            assert (Path(temp_dir) / "new_dir").exists()
            assert (Path(temp_dir) / "new_dir" / "file.txt").exists()

    def test_rename_files__nonexistent_source(self):
        """Test _rename_files with nonexistent source file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            task_config = TaskConfig(
                {
                    "options": {
                        "repo_url": self.repo_url,
                        "target_directory": temp_dir,
                        "renames": [
                            {"local": "nonexistent.txt", "target": "new_file.txt"},
                        ],
                    }
                }
            )
            task = DownloadExtract(self.project_config, task_config)

            # Should not raise error
            task._rename_files(temp_dir)

            # Target should not exist
            assert not (Path(temp_dir) / "new_file.txt").exists()

    def test_rename_files__with_subdirectories(self):
        """Test _rename_files creating subdirectories"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "file.txt"
            test_file.write_text("test content")

            task_config = TaskConfig(
                {
                    "options": {
                        "repo_url": self.repo_url,
                        "target_directory": temp_dir,
                        "renames": [
                            {"local": "file.txt", "target": "subdir/nested/file.txt"},
                        ],
                    }
                }
            )
            task = DownloadExtract(self.project_config, task_config)

            task._rename_files(temp_dir)

            assert not test_file.exists()
            assert (Path(temp_dir) / "subdir" / "nested" / "file.txt").exists()

    @mock.patch("cumulusci.tasks.vcs.download_extract.download_extract_vcs_from_repo")
    def test_download_repo_and_extract__no_include(self, mock_download_extract):
        """Test _download_repo_and_extract without include filter"""
        mock_zf = mock.Mock()
        mock_zf.namelist.return_value = ["file1.txt", "file2.txt", "dir/file3.txt"]
        mock_download_extract.return_value = mock_zf

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock.Mock()
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            task._download_repo_and_extract(temp_dir)

            mock_download_extract.assert_called_once_with(
                task.repo, subfolder=None, ref="abc123"
            )
            mock_zf.extractall.assert_called_once_with(
                path=temp_dir, members=["file1.txt", "file2.txt", "dir/file3.txt"]
            )
            mock_zf.close.assert_called_once()

    @mock.patch("cumulusci.tasks.vcs.download_extract.download_extract_vcs_from_repo")
    @mock.patch("cumulusci.tasks.vcs.download_extract.filter_namelist")
    def test_download_repo_and_extract__with_include(
        self, mock_filter, mock_download_extract
    ):
        """Test _download_repo_and_extract with include filter"""
        mock_zf = mock.Mock()
        mock_zf.namelist.return_value = ["file1.txt", "file2.txt", "dir/file3.txt"]
        mock_download_extract.return_value = mock_zf
        mock_filter.return_value = ["file1.txt", "dir/file3.txt"]

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "include": ["file1.txt", "dir/"],
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock.Mock()
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            task._download_repo_and_extract(temp_dir)

            mock_filter.assert_called_once_with(
                includes=["file1.txt", "dir/"],
                namelist=["file1.txt", "file2.txt", "dir/file3.txt"],
            )
            mock_zf.extractall.assert_called_once_with(
                path=temp_dir, members=["file1.txt", "dir/file3.txt"]
            )

    @mock.patch("cumulusci.tasks.vcs.download_extract.download_extract_vcs_from_repo")
    def test_download_repo_and_extract__with_subfolder(self, mock_download_extract):
        """Test _download_repo_and_extract with subfolder"""
        mock_zf = mock.Mock()
        mock_zf.namelist.return_value = ["file1.txt"]
        mock_download_extract.return_value = mock_zf

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "sub_folder": "src",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.repo = mock.Mock()
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            task._download_repo_and_extract(temp_dir)

            mock_download_extract.assert_called_once_with(
                task.repo, subfolder="src", ref="abc123"
            )

    def test_check_latest_commit__force_true(self):
        """Test _check_latest_commit with force=True always downloads"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "force": True,
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(task, "_init_repo") as mock_init:
            result = task._check_latest_commit()

            assert result is True
            mock_init.assert_called_once()

    def test_check_latest_commit__no_tracking_entry(self):
        """Test _check_latest_commit when no tracking entry exists (fresh run)"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(task, "_load_tracking_entry", return_value={}):
            with mock.patch.object(task, "_init_repo"):
                task.commit = "new_commit"
                result = task._check_latest_commit()

                assert result is True

    @mock.patch("time.time")
    def test_check_latest_commit__recent_timestamp(self, mock_time):
        """Test _check_latest_commit skips repo check within 1-hour window"""
        mock_time.return_value = 1000

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(
            task,
            "_load_tracking_entry",
            return_value={"timestamp": 999, "commit": "abc123"},
        ):
            result = task._check_latest_commit()

            assert result is False

    @mock.patch("time.time")
    def test_check_latest_commit__old_timestamp_same_commit(self, mock_time):
        """Test _check_latest_commit with expired window but same commit"""
        mock_time.return_value = 5000

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(
            task,
            "_load_tracking_entry",
            return_value={"timestamp": 1000, "commit": "abc123"},
        ):
            with mock.patch.object(task, "_init_repo") as mock_init:
                task.commit = "abc123"
                result = task._check_latest_commit()

                assert result is False
                mock_init.assert_called_once()

    @mock.patch("time.time")
    def test_check_latest_commit__old_timestamp_different_commit(self, mock_time):
        """Test _check_latest_commit with expired window and new commit available"""
        mock_time.return_value = 5000

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(
            task,
            "_load_tracking_entry",
            return_value={"timestamp": 1000, "commit": "old_commit"},
        ):
            with mock.patch.object(task, "_init_repo") as mock_init:
                task.commit = "new_commit"
                result = task._check_latest_commit()

                assert result is True
                mock_init.assert_called_once()

    @mock.patch("time.time")
    def test_check_latest_commit__missing_timestamp_key(self, mock_time):
        """Test _check_latest_commit with missing timestamp defaults to 0 (always expired)"""
        mock_time.return_value = 5000

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(
            task, "_load_tracking_entry", return_value={"commit": "old_commit"}
        ):
            with mock.patch.object(task, "_init_repo") as mock_init:
                task.commit = "new_commit"
                result = task._check_latest_commit()

                assert result is True
                mock_init.assert_called_once()

    @mock.patch("time.time")
    def test_check_latest_commit__missing_commit_key(self, mock_time):
        """Test _check_latest_commit with missing commit defaults to empty string"""
        mock_time.return_value = 5000

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(
            task, "_load_tracking_entry", return_value={"timestamp": 1000}
        ):
            with mock.patch.object(task, "_init_repo") as mock_init:
                task.commit = "abc123"
                result = task._check_latest_commit()

                assert result is True
                mock_init.assert_called_once()

    def test_run_task__skip_no_changes(self):
        """Test _run_task skipping download when no changes"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with mock.patch.object(task, "_check_latest_commit", return_value=False):
            with mock.patch.object(task, "_set_target_directory") as mock_set_target:
                task()

                mock_set_target.assert_called_once()

    def test_run_task__create_target_directory(self):
        """Test _run_task creates the target directory when it does not exist"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "test_dir")
            task.parsed_options.target_directory = target_dir

            assert not os.path.exists(target_dir)

            with mock.patch.object(task, "_check_latest_commit", return_value=True):
                with mock.patch.object(task, "_set_target_directory"):
                    with mock.patch.object(task, "_download_repo_and_extract"):
                        with mock.patch.object(task, "_rename_files"):
                            with mock.patch.object(task, "_save_tracking_entry"):
                                task()

                                assert os.path.exists(target_dir)

    def test_run_task__full_run(self):
        """Test _run_task calls all steps in order and saves tracking entry"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "test_dir")
            task.parsed_options.target_directory = target_dir

            with mock.patch.object(task, "_check_latest_commit", return_value=True):
                with mock.patch.object(task, "_set_target_directory"):
                    with mock.patch.object(
                        task, "_download_repo_and_extract"
                    ) as mock_download:
                        with mock.patch.object(task, "_rename_files") as mock_rename:
                            with mock.patch.object(
                                task, "_save_tracking_entry"
                            ) as mock_save:
                                task()

                                mock_download.assert_called_once_with(Path(target_dir))
                                mock_rename.assert_called_once_with(Path(target_dir))
                                mock_save.assert_called_once()

    def test_run_task__force_download(self):
        """Test _run_task with force=True proceeds regardless of tracking state"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                    "force": True,
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = os.path.join(temp_dir, "test_dir")
            task.parsed_options.target_directory = target_dir

            with mock.patch.object(task, "_check_latest_commit", return_value=True):
                with mock.patch.object(task, "_set_target_directory"):
                    with mock.patch.object(task, "_download_repo_and_extract"):
                        with mock.patch.object(task, "_rename_files"):
                            with mock.patch.object(task, "_save_tracking_entry"):
                                task()

                                assert task.parsed_options.force is True

    # -------------------------------------------------------------------------
    # Tracking file helpers
    # -------------------------------------------------------------------------

    def test_get_tracking_file_path(self):
        """Test _get_tracking_file_path returns path inside project_local_dir"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "test_dir",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                type(task.project_config),
                "project_local_dir",
                new_callable=mock.PropertyMock,
                return_value=temp_dir,
            ):
                result = task._get_tracking_file_path()

                assert result == Path(temp_dir) / TRACKING_FILE_NAME

    def test_load_tracking_entry__file_not_exists(self):
        """Test _load_tracking_entry returns empty dict when tracking file is absent"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"

        with tempfile.TemporaryDirectory() as temp_dir:
            tracking_path = Path(temp_dir) / TRACKING_FILE_NAME
            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=tracking_path
            ):
                result = task._load_tracking_entry()

                assert result == {}

    def test_load_tracking_entry__entry_exists(self):
        """Test _load_tracking_entry returns the correct entry for the target directory"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"

        with tempfile.TemporaryDirectory() as temp_dir:
            tracking_path = Path(temp_dir) / TRACKING_FILE_NAME
            tracking_path.write_text(
                json.dumps(
                    {
                        "/some/target": {"commit": "abc123", "timestamp": 1000.0},
                        "/other/target": {"commit": "def456", "timestamp": 2000.0},
                    }
                )
            )
            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=tracking_path
            ):
                result = task._load_tracking_entry()

                assert result == {"commit": "abc123", "timestamp": 1000.0}

    def test_load_tracking_entry__entry_missing_for_target(self):
        """Test _load_tracking_entry returns empty dict when file exists but has no entry for target"""
        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"

        with tempfile.TemporaryDirectory() as temp_dir:
            tracking_path = Path(temp_dir) / TRACKING_FILE_NAME
            tracking_path.write_text(
                json.dumps({"/other/target": {"commit": "def456", "timestamp": 2000.0}})
            )
            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=tracking_path
            ):
                result = task._load_tracking_entry()

                assert result == {}

    @mock.patch("time.time")
    def test_save_tracking_entry__creates_new_file(self, mock_time):
        """Test _save_tracking_entry writes a new JSON file when none exists"""
        mock_time.return_value = 1000.0

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            tracking_path = Path(temp_dir) / TRACKING_FILE_NAME
            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=tracking_path
            ):
                task._save_tracking_entry()

                assert tracking_path.exists()
                data = json.loads(tracking_path.read_text())
                assert data == {
                    "/some/target": {"commit": "abc123", "timestamp": 1000.0}
                }

    @mock.patch("time.time")
    def test_save_tracking_entry__updates_existing_entry(self, mock_time):
        """Test _save_tracking_entry updates only the target entry, preserving others"""
        mock_time.return_value = 2000.0

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"
        task.commit = "new_commit"

        with tempfile.TemporaryDirectory() as temp_dir:
            tracking_path = Path(temp_dir) / TRACKING_FILE_NAME
            tracking_path.write_text(
                json.dumps(
                    {
                        "/some/target": {"commit": "old_commit", "timestamp": 500.0},
                        "/other/target": {"commit": "def456", "timestamp": 500.0},
                    }
                )
            )
            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=tracking_path
            ):
                task._save_tracking_entry()

                data = json.loads(tracking_path.read_text())
                assert data["/some/target"] == {
                    "commit": "new_commit",
                    "timestamp": 2000.0,
                }
                assert data["/other/target"] == {"commit": "def456", "timestamp": 500.0}

    @mock.patch("time.time")
    def test_save_tracking_entry__creates_parent_dir(self, mock_time):
        """Test _save_tracking_entry creates parent directories if they do not exist"""
        mock_time.return_value = 1000.0

        task_config = TaskConfig(
            {
                "options": {
                    "repo_url": self.repo_url,
                    "target_directory": "/some/target",
                }
            }
        )
        task = DownloadExtract(self.project_config, task_config)
        task.parsed_options.target_directory = "/some/target"
        task.commit = "abc123"

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "local" / TRACKING_FILE_NAME
            assert not nested_path.parent.exists()

            with mock.patch.object(
                task, "_get_tracking_file_path", return_value=nested_path
            ):
                task._save_tracking_entry()

                assert nested_path.exists()
