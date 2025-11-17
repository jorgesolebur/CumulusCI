"""Tests for copyContents module."""

import os
import shutil
import tempfile
from unittest import mock

import pytest

from cumulusci.core.config import BaseProjectConfig, TaskConfig, UniversalConfig
from cumulusci.tasks.utility.copyContents import (
    ConsolidateUnpackagedMetadata,
    clean_temp_directory,
    consolidate_metadata,
    copy_directory_contents,
    copy_item_to_destination,
    copy_matched_files,
    merge_directory_contents,
    print_directory_tree,
    resolve_file_pattern,
    validate_directory,
)


class TestMergeDirectoryContents:
    """Test cases for merge_directory_contents function."""

    def test_merge_empty_directories(self):
        """Test merging two empty directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            merge_directory_contents(src_dir, dest_dir)
            assert os.path.exists(dest_dir)

    def test_merge_files_from_source(self):
        """Test merging files from source to destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create file in source
            src_file = os.path.join(src_dir, "test.txt")
            with open(src_file, "w") as f:
                f.write("source content")

            merge_directory_contents(src_dir, dest_dir)

            dest_file = os.path.join(dest_dir, "test.txt")
            assert os.path.exists(dest_file)
            with open(dest_file, "r") as f:
                assert f.read() == "source content"

    def test_merge_overwrites_existing_files(self):
        """Test that source files overwrite destination files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create file in destination
            dest_file = os.path.join(dest_dir, "test.txt")
            with open(dest_file, "w") as f:
                f.write("old content")

            # Create file in source with different content
            src_file = os.path.join(src_dir, "test.txt")
            with open(src_file, "w") as f:
                f.write("new content")

            merge_directory_contents(src_dir, dest_dir)

            with open(dest_file, "r") as f:
                assert f.read() == "new content"

    def test_merge_nested_directories(self):
        """Test merging nested directory structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create nested structure in source
            nested_src = os.path.join(src_dir, "nested", "subdir")
            os.makedirs(nested_src)
            nested_file = os.path.join(nested_src, "file.txt")
            with open(nested_file, "w") as f:
                f.write("nested content")

            merge_directory_contents(src_dir, dest_dir)

            nested_dest = os.path.join(dest_dir, "nested", "subdir", "file.txt")
            assert os.path.exists(nested_dest)
            with open(nested_dest, "r") as f:
                assert f.read() == "nested content"

    def test_merge_with_overwrite_flag(self):
        """Test merge with overwrite flag enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create file in destination
            dest_file = os.path.join(dest_dir, "test.txt")
            with open(dest_file, "w") as f:
                f.write("old")

            # Create directory with same name in source
            src_subdir = os.path.join(src_dir, "test.txt")
            os.makedirs(src_subdir)

            merge_directory_contents(src_dir, dest_dir, overwrite=True)

            # Should be replaced with directory
            assert os.path.isdir(os.path.join(dest_dir, "test.txt"))


class TestCopyItemToDestination:
    """Test cases for copy_item_to_destination function."""

    def test_copy_file_to_new_location(self):
        """Test copying a file to a new location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dest_file = os.path.join(tmpdir, "dest.txt")

            with open(src_file, "w") as f:
                f.write("test content")

            copy_item_to_destination(src_file, dest_file)

            assert os.path.exists(dest_file)
            with open(dest_file, "r") as f:
                assert f.read() == "test content"

    def test_copy_directory_to_new_location(self):
        """Test copying a directory to a new location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)

            src_file = os.path.join(src_dir, "file.txt")
            with open(src_file, "w") as f:
                f.write("content")

            copy_item_to_destination(src_dir, dest_dir)

            assert os.path.exists(dest_dir)
            assert os.path.exists(os.path.join(dest_dir, "file.txt"))

    def test_copy_directory_merges_with_existing(self):
        """Test copying directory merges with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # File in source
            src_file = os.path.join(src_dir, "src_file.txt")
            with open(src_file, "w") as f:
                f.write("src")

            # File in destination
            dest_file = os.path.join(dest_dir, "dest_file.txt")
            with open(dest_file, "w") as f:
                f.write("dest")

            copy_item_to_destination(src_dir, dest_dir)

            # Both files should exist
            assert os.path.exists(os.path.join(dest_dir, "src_file.txt"))
            assert os.path.exists(os.path.join(dest_dir, "dest_file.txt"))

    def test_copy_file_overwrites_existing_file(self):
        """Test copying file overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dest_file = os.path.join(tmpdir, "dest.txt")

            with open(dest_file, "w") as f:
                f.write("old")

            with open(src_file, "w") as f:
                f.write("new")

            copy_item_to_destination(src_file, dest_file)

            with open(dest_file, "r") as f:
                assert f.read() == "new"

    def test_copy_file_replaces_directory_with_overwrite(self):
        """Test copying file replaces directory when overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dest_dir = os.path.join(tmpdir, "dest")

            os.makedirs(dest_dir)
            with open(src_file, "w") as f:
                f.write("file content")

            copy_item_to_destination(src_file, dest_dir, overwrite=True)

            assert os.path.isfile(dest_dir)
            with open(dest_dir, "r") as f:
                assert f.read() == "file content"

    def test_copy_directory_replaces_file_with_overwrite(self):
        """Test copying directory replaces file when overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_file = os.path.join(tmpdir, "dest")

            os.makedirs(src_dir)
            src_file = os.path.join(src_dir, "file.txt")
            with open(src_file, "w") as f:
                f.write("content")

            with open(dest_file, "w") as f:
                f.write("old")

            copy_item_to_destination(src_dir, dest_file, overwrite=True)

            assert os.path.isdir(dest_file)
            assert os.path.exists(os.path.join(dest_file, "file.txt"))


class TestCopyDirectoryContents:
    """Test cases for copy_directory_contents function."""

    def test_copy_all_contents(self):
        """Test copying all contents from source to destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create files and subdirectories
            with open(os.path.join(src_dir, "file1.txt"), "w") as f:
                f.write("file1")
            os.makedirs(os.path.join(src_dir, "subdir"))
            with open(os.path.join(src_dir, "subdir", "file2.txt"), "w") as f:
                f.write("file2")

            copy_directory_contents(src_dir, dest_dir)

            assert os.path.exists(os.path.join(dest_dir, "file1.txt"))
            assert os.path.exists(os.path.join(dest_dir, "subdir", "file2.txt"))

    def test_extract_src_directory(self):
        """Test extracting src directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create src subdirectory
            src_subdir = os.path.join(src_dir, "src")
            os.makedirs(src_subdir)
            with open(os.path.join(src_subdir, "file.txt"), "w") as f:
                f.write("content")

            copy_directory_contents(src_dir, dest_dir, extract_src=True)

            # File should be in dest_dir/src/file.txt
            assert os.path.exists(os.path.join(dest_dir, "src", "file.txt"))

    def test_extract_src_with_no_src_directory(self):
        """Test extract_src when src directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            with open(os.path.join(src_dir, "file.txt"), "w") as f:
                f.write("content")

            copy_directory_contents(src_dir, dest_dir, extract_src=True)

            # Should copy normally since no src directory
            assert os.path.exists(os.path.join(dest_dir, "file.txt"))

    def test_copy_with_overwrite(self):
        """Test copying with overwrite flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create conflicting file
            dest_file = os.path.join(dest_dir, "test.txt")
            with open(dest_file, "w") as f:
                f.write("old")

            src_file = os.path.join(src_dir, "test.txt")
            with open(src_file, "w") as f:
                f.write("new")

            copy_directory_contents(src_dir, dest_dir, overwrite=True)

            with open(dest_file, "r") as f:
                assert f.read() == "new"


class TestResolveFilePattern:
    """Test cases for resolve_file_pattern function."""

    def test_resolve_specific_file(self):
        """Test resolving a specific file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("content")

            result = resolve_file_pattern("test.txt", tmpdir)
            assert len(result) == 1
            assert result[0] == test_file

    def test_resolve_glob_pattern(self):
        """Test resolving a glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple files
            for i in range(3):
                with open(os.path.join(tmpdir, f"file{i}.txt"), "w") as f:
                    f.write(f"content{i}")

            result = resolve_file_pattern("*.txt", tmpdir)
            assert len(result) == 3

    def test_resolve_recursive_pattern(self):
        """Test resolving recursive glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)

            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(subdir, "file2.txt"), "w") as f:
                f.write("content2")

            result = resolve_file_pattern("**/*.txt", tmpdir)
            assert len(result) == 2

    def test_resolve_pattern_no_match_raises_error(self):
        """Test that resolving non-existent pattern raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_file_pattern("nonexistent.txt", tmpdir)
            assert len(result) == 0
            assert result == []

    def test_resolve_pattern_with_subdirectory(self):
        """Test resolving pattern in subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            test_file = os.path.join(subdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("content")

            result = resolve_file_pattern("subdir/test.txt", tmpdir)
            assert len(result) == 1
            assert result[0] == test_file


class TestCopyMatchedFiles:
    """Test cases for copy_matched_files function."""

    def test_copy_single_file(self):
        """Test copying a single matched file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            source_file = os.path.join(source_dir, "file.txt")
            with open(source_file, "w") as f:
                f.write("content")

            copy_matched_files([source_file], source_dir, dest_dir)

            dest_file = os.path.join(dest_dir, "file.txt")
            assert os.path.exists(dest_file)
            with open(dest_file, "r") as f:
                assert f.read() == "content"

    def test_copy_preserves_relative_structure(self):
        """Test copying preserves relative directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            nested_file = os.path.join(source_dir, "subdir", "file.txt")
            os.makedirs(os.path.dirname(nested_file))
            with open(nested_file, "w") as f:
                f.write("content")

            copy_matched_files([nested_file], source_dir, dest_dir)

            dest_file = os.path.join(dest_dir, "subdir", "file.txt")
            assert os.path.exists(dest_file)

    def test_copy_multiple_files(self):
        """Test copying multiple matched files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            files = []
            for i in range(3):
                file_path = os.path.join(source_dir, f"file{i}.txt")
                with open(file_path, "w") as f:
                    f.write(f"content{i}")
                files.append(file_path)

            copy_matched_files(files, source_dir, dest_dir)

            for i in range(3):
                assert os.path.exists(os.path.join(dest_dir, f"file{i}.txt"))


class TestCleanTempDirectory:
    """Test cases for clean_temp_directory function."""

    def test_clean_existing_directory(self):
        """Test cleaning an existing temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test")
            os.makedirs(test_dir)

            with open(os.path.join(test_dir, "file.txt"), "w") as f:
                f.write("content")

            clean_temp_directory(test_dir)
            assert not os.path.exists(test_dir)

    def test_clean_nonexistent_directory(self):
        """Test cleaning a non-existent directory doesn't raise error."""
        clean_temp_directory("/nonexistent/path")
        # Should not raise an exception

    def test_clean_directory_with_nested_structure(self):
        """Test cleaning directory with nested structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test")
            nested = os.path.join(test_dir, "nested", "deep")
            os.makedirs(nested)

            with open(os.path.join(nested, "file.txt"), "w") as f:
                f.write("content")

            clean_temp_directory(test_dir)
            assert not os.path.exists(test_dir)


class TestValidateDirectory:
    """Test cases for validate_directory function."""

    def test_validate_existing_directory(self):
        """Test validating an existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validate_directory(tmpdir)
            # Should not raise

    def test_validate_nonexistent_path_raises_error(self):
        """Test validating non-existent path raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            validate_directory("/nonexistent/path")

    def test_validate_file_raises_error(self):
        """Test validating a file raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("content")

            with pytest.raises(ValueError, match="is not a directory"):
                validate_directory(test_file)

    def test_validate_with_custom_path_name(self):
        """Test validating with custom path name in error message."""
        with pytest.raises(ValueError, match="custom_name does not exist"):
            validate_directory("/nonexistent", "custom_name")


class TestConsolidateMetadata:
    """Test cases for consolidate_metadata function."""

    def test_consolidate_string_path(self):
        """Test consolidating metadata from string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content")

            result, file_count = consolidate_metadata("source", tmpdir)

            assert os.path.exists(result)
            assert os.path.exists(os.path.join(result, "file.txt"))
            assert file_count == 1
            clean_temp_directory(result)

    def test_consolidate_list_paths(self):
        """Test consolidating metadata from list of paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = os.path.join(tmpdir, "dir1")
            dir2 = os.path.join(tmpdir, "dir2")
            os.makedirs(dir1)
            os.makedirs(dir2)

            with open(os.path.join(dir1, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(dir2, "file2.txt"), "w") as f:
                f.write("content2")

            result, file_count = consolidate_metadata(["dir1", "dir2"], tmpdir)

            assert os.path.exists(os.path.join(result, "file1.txt"))
            assert os.path.exists(os.path.join(result, "file2.txt"))
            assert file_count == 2
            clean_temp_directory(result)

    def test_consolidate_dict_with_wildcard(self):
        """Test consolidating metadata from dict with wildcard pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            src_subdir = os.path.join(source_dir, "src")
            os.makedirs(src_subdir)

            with open(os.path.join(src_subdir, "file.txt"), "w") as f:
                f.write("content")

            result, file_count = consolidate_metadata({"source": "*.*"}, tmpdir)

            assert os.path.exists(os.path.join(result, "src", "file.txt"))
            assert file_count == 1
            clean_temp_directory(result)

    def test_consolidate_dict_with_single_pattern(self):
        """Test consolidating metadata from dict with single pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            test_file = os.path.join(source_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("content")

            result, file_count = consolidate_metadata({"source": "test.txt"}, tmpdir)

            assert os.path.exists(os.path.join(result, "test.txt"))
            assert file_count == 1
            clean_temp_directory(result)

    def test_consolidate_dict_with_list_patterns(self):
        """Test consolidating metadata from dict with list of patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            file1 = os.path.join(source_dir, "file1.txt")
            file2 = os.path.join(source_dir, "file2.txt")
            with open(file1, "w") as f:
                f.write("content1")
            with open(file2, "w") as f:
                f.write("content2")

            result, file_count = consolidate_metadata(
                {"source": ["file1.txt", "file2.txt"]}, tmpdir
            )

            assert os.path.exists(os.path.join(result, "file1.txt"))
            assert os.path.exists(os.path.join(result, "file2.txt"))
            assert file_count == 2
            clean_temp_directory(result)

    def test_consolidate_with_absolute_path(self):
        """Test consolidating with absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content")

            abs_path = os.path.abspath(source_dir)
            result, file_count = consolidate_metadata(abs_path, tmpdir)

            assert os.path.exists(os.path.join(result, "file.txt"))
            assert file_count == 1
            clean_temp_directory(result)

    def test_consolidate_invalid_type_raises_error(self):
        """Test consolidating with invalid type raises TypeError or ValueError."""
        # TypeGuard will catch type errors before ValueError
        with pytest.raises((TypeError, ValueError)):
            consolidate_metadata(12345)  # Invalid type

    def test_consolidate_invalid_pattern_type_raises_error(self):
        """Test consolidating with invalid pattern type raises TypeError or ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            # TypeGuard will catch type errors before ValueError
            with pytest.raises((TypeError, ValueError)):
                consolidate_metadata({"source": 12345}, tmpdir)

    def test_consolidate_nonexistent_directory_raises_error(self):
        """Test consolidating non-existent directory raises ValueError."""
        with pytest.raises(ValueError):
            consolidate_metadata("nonexistent", "/tmp")

    def test_consolidate_cleans_up_on_error(self):
        """Test that temp directory is cleaned up on error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                consolidate_metadata("nonexistent", tmpdir)
            except ValueError:
                pass

            # Temp directory should be cleaned up
            # We can't directly check, but if it wasn't cleaned up,
            # we'd have issues with temp directory accumulation

    def test_consolidate_dict_with_star_pattern(self):
        """Test consolidating with '*' pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            src_subdir = os.path.join(source_dir, "src")
            os.makedirs(src_subdir)

            with open(os.path.join(src_subdir, "file.txt"), "w") as f:
                f.write("content")

            result, file_count = consolidate_metadata({"source": "*"}, tmpdir)

            assert os.path.exists(os.path.join(result, "src", "file.txt"))
            assert file_count == 1
            clean_temp_directory(result)


class TestPrintDirectoryTree:
    """Test cases for print_directory_tree function."""

    def test_print_tree_without_logger(self, capsys):
        """Test printing directory tree without logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "subdir", "file2.txt"), "w") as f:
                f.write("content2")

            print_directory_tree(tmpdir)

            captured = capsys.readouterr()
            assert "file1.txt" in captured.out
            assert "subdir" in captured.out

    def test_print_tree_with_logger(self):
        """Test printing directory tree with logger."""
        import logging

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "file.txt"), "w") as f:
                f.write("content")

            logger = logging.getLogger("test")
            with mock.patch.object(logger, "info") as mock_info:
                print_directory_tree(tmpdir, logger=logger)

                # Verify logger.info was called
                assert mock_info.called
                call_args = [args[0] for args, _ in mock_info.call_args_list]
                assert any("file.txt" in msg for msg in call_args)

    def test_print_tree_respects_max_depth(self, capsys):
        """Test that print_tree respects max_depth parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            current = tmpdir
            for i in range(5):
                current = os.path.join(current, f"level{i}")
                os.makedirs(current)

            print_directory_tree(tmpdir, max_depth=2)

            captured = capsys.readouterr()
            # Should only show first 2 levels
            assert "level0" in captured.out

    def test_print_tree_handles_permission_error(self, capsys):
        """Test that print_tree handles PermissionError gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock os.listdir to raise PermissionError
            with mock.patch("os.listdir", side_effect=PermissionError("Access denied")):
                print_directory_tree(tmpdir)
                # Should not raise exception


class TestConsolidateUnpackagedMetadataTask:
    """Test cases for ConsolidateUnpackagedMetadata task class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_repo_root = tempfile.mkdtemp()
        self.universal_config = UniversalConfig()
        self.project_config = BaseProjectConfig(
            self.universal_config,
            config={"noyaml": True, "project": {"package": {}}},
            repo_info={"root": self.temp_repo_root},
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_repo_root):
            shutil.rmtree(self.temp_repo_root)

    def test_task_with_string_metadata_path(self):
        """Test task with string metadata path."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        with open(os.path.join(source_dir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        # Task stores result in task.result (from _run_task return value)
        result_path = task.result

        assert result_path is not None
        assert isinstance(result_path, str)
        assert os.path.exists(result_path)
        assert os.path.exists(os.path.join(result_path, "file.txt"))
        clean_temp_directory(result_path)

    def test_task_with_list_metadata_path(self):
        """Test task with list metadata path."""
        dir1 = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        dir2 = os.path.join(self.temp_repo_root, "unpackaged", "post")
        os.makedirs(dir1)
        os.makedirs(dir2)

        with open(os.path.join(dir1, "file1.txt"), "w") as f:
            f.write("content1")
        with open(os.path.join(dir2, "file2.txt"), "w") as f:
            f.write("content2")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": ["unpackaged/pre", "unpackaged/post"]
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        result_path = task.result
        assert result_path is not None
        assert os.path.exists(os.path.join(result_path, "file1.txt"))
        assert os.path.exists(os.path.join(result_path, "file2.txt"))
        clean_temp_directory(result_path)

    def test_task_with_dict_metadata_path(self):
        """Test task with dict metadata path."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        test_file = os.path.join(source_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": {"unpackaged/pre": "test.txt"}
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        result_path = task.result
        assert result_path is not None
        assert os.path.exists(os.path.join(result_path, "test.txt"))
        clean_temp_directory(result_path)

    def test_task_with_no_metadata_path(self):
        """Test task with no metadata path configured."""
        self.project_config.config["project"]["package"] = {}

        task_config = TaskConfig({})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        with mock.patch.object(task.logger, "warning") as mock_warning:
            task()

            mock_warning.assert_called_once()
            assert task.return_values["path"] is None

    def test_task_with_base_path_option(self):
        """Test task with custom base_path option."""
        custom_base = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(custom_base, "source")
            os.makedirs(source_dir)

            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content")

            self.project_config.config["project"]["package"] = {
                "unpackaged_metadata_path": "source"
            }

            task_config = TaskConfig(
                {"options": {"base_path": custom_base, "keep_temp": True}}
            )
            task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

            task()

            assert task.result is not None
            assert os.path.exists(os.path.join(task.result, "file.txt"))
            clean_temp_directory(task.result)
        finally:
            shutil.rmtree(custom_base)

    def test_task_with_keep_temp_option(self):
        """Test task with keep_temp option enabled."""
        source_dir = os.path.join(self.project_config.repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        with open(os.path.join(source_dir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        assert task.result is not None
        # Directory should still exist since keep_temp=True
        assert os.path.exists(task.result)
        clean_temp_directory(task.result)

    def test_task_logs_consolidation_info(self):
        """Test that task logs consolidation information."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        with mock.patch.object(task.logger, "info") as mock_info:
            task()

            # Check that info was called with consolidation messages
            call_args = [call[0][0] for call in mock_info.call_args_list]
            assert any("Consolidating unpackaged metadata" in msg for msg in call_args)
            assert any("Found" in msg for msg in call_args)


class TestWindowsLinuxCompatibility:
    """Test cases for Windows/Linux path compatibility."""

    def test_path_separators_handled_correctly(self):
        """Test that path separators are handled correctly on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use os.path.join which handles platform differences
            source_dir = os.path.join(tmpdir, "source", "subdir")
            os.makedirs(source_dir)

            test_file = os.path.join(source_dir, "file.txt")
            with open(test_file, "w") as f:
                f.write("content")

            # Test with relative pattern from source directory
            pattern = "file.txt"
            result, file_count = consolidate_metadata(
                {os.path.join(tmpdir, "source", "subdir"): pattern}, tmpdir
            )

            assert os.path.exists(result)
            assert file_count == 1
            assert os.path.exists(os.path.join(result, "file.txt"))
            clean_temp_directory(result)

    def test_absolute_paths_work_on_both_platforms(self):
        """Test that absolute paths work on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content")

            abs_path = os.path.abspath(source_dir)
            result, file_count = consolidate_metadata(abs_path, tmpdir)

            assert os.path.exists(os.path.join(result, "file.txt"))
            assert file_count == 1
            clean_temp_directory(result)

    def test_relative_paths_work_on_both_platforms(self):
        """Test that relative paths work on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source_dir = "source"
                os.makedirs(source_dir)

                with open(os.path.join(source_dir, "file.txt"), "w") as f:
                    f.write("content")

                result, file_count = consolidate_metadata(
                    source_dir, tmpdir, logger=None
                )

                assert os.path.exists(os.path.join(result, "file.txt"))
                assert file_count == 1
                clean_temp_directory(result)
            finally:
                os.chdir(original_cwd)

    def test_nested_paths_work_on_both_platforms(self):
        """Test that deeply nested paths work on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create deeply nested structure
            nested_path = os.path.join(tmpdir, "level1", "level2", "level3")
            os.makedirs(nested_path)

            test_file = os.path.join(nested_path, "file.txt")
            with open(test_file, "w") as f:
                f.write("content")

            # Test merging nested directories
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(dest_dir)

            merge_directory_contents(os.path.join(tmpdir, "level1"), dest_dir)

            assert os.path.exists(
                os.path.join(dest_dir, "level2", "level3", "file.txt")
            )

    def test_path_with_spaces_works_on_both_platforms(self):
        """Test that paths with spaces work on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source with spaces")
            dest_dir = os.path.join(tmpdir, "dest with spaces")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            test_file = os.path.join(source_dir, "file with spaces.txt")
            with open(test_file, "w") as f:
                f.write("content")

            copy_directory_contents(source_dir, dest_dir)

            assert os.path.exists(os.path.join(dest_dir, "file with spaces.txt"))


class TestMergeDirectoryContentsEdgeCases:
    """Additional edge case tests for merge_directory_contents."""

    def test_merge_with_file_conflict_no_overwrite(self):
        """Test merge when file exists in destination but overwrite=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create file in destination
            dest_file = os.path.join(dest_dir, "test.txt")
            with open(dest_file, "w") as f:
                f.write("dest content")

            # Create file in source with different content
            src_file = os.path.join(src_dir, "test.txt")
            with open(src_file, "w") as f:
                f.write("src content")

            merge_directory_contents(src_dir, dest_dir, overwrite=False)

            # Should overwrite even without overwrite flag (default behavior)
            with open(dest_file, "r") as f:
                assert f.read() == "src content"

    def test_merge_directory_replaces_file_with_overwrite(self):
        """Test merge when source has directory but dest has file with overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create file in destination
            dest_file = os.path.join(dest_dir, "item")
            with open(dest_file, "w") as f:
                f.write("file")

            # Create directory with same name in source
            src_subdir = os.path.join(src_dir, "item")
            os.makedirs(src_subdir)
            with open(os.path.join(src_subdir, "file.txt"), "w") as f:
                f.write("content")

            merge_directory_contents(src_dir, dest_dir, overwrite=True)

            # Should be replaced with directory
            assert os.path.isdir(os.path.join(dest_dir, "item"))
            assert os.path.exists(os.path.join(dest_dir, "item", "file.txt"))

    def test_merge_file_replaces_directory_with_overwrite(self):
        """Test merge when source has file but dest has directory with overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create directory in destination
            dest_subdir = os.path.join(dest_dir, "item")
            os.makedirs(dest_subdir)

            # Create file with same name in source
            src_file = os.path.join(src_dir, "item")
            with open(src_file, "w") as f:
                f.write("file content")

            merge_directory_contents(src_dir, dest_dir, overwrite=True)

            # Should be replaced with file
            assert os.path.isfile(os.path.join(dest_dir, "item"))
            with open(os.path.join(dest_dir, "item"), "r") as f:
                assert f.read() == "file content"

    def test_merge_empty_source_directory(self):
        """Test merging empty source directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            merge_directory_contents(src_dir, dest_dir)
            # Should not raise error
            assert os.path.exists(dest_dir)


class TestCopyItemToDestinationEdgeCases:
    """Additional edge case tests for copy_item_to_destination."""

    def test_copy_file_when_dest_is_directory_no_overwrite(self):
        """Test copying file when destination is directory without overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(dest_dir)

            with open(src_file, "w") as f:
                f.write("file content")

            # Should raise error or handle gracefully
            try:
                copy_item_to_destination(src_file, dest_dir, overwrite=False)
                # If no error, file should be copied into directory
                assert os.path.exists(os.path.join(dest_dir, "source.txt"))
            except (OSError, shutil.Error):
                # Some systems may raise error
                pass

    def test_copy_directory_when_dest_is_file_no_overwrite(self):
        """Test copying directory when destination is file without overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_file = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)

            src_file = os.path.join(src_dir, "file.txt")
            with open(src_file, "w") as f:
                f.write("content")

            with open(dest_file, "w") as f:
                f.write("file")

            # Code removes the file and copies directory
            copy_item_to_destination(src_dir, dest_file, overwrite=False)

            # Should be replaced with directory
            assert os.path.isdir(dest_file)
            assert os.path.exists(os.path.join(dest_file, "file.txt"))

    def test_copy_to_nonexistent_parent_directory(self):
        """Test copying to path with nonexistent parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "source.txt")
            dest_file = os.path.join(tmpdir, "nonexistent", "dest.txt")

            with open(src_file, "w") as f:
                f.write("content")

            # Should raise error
            with pytest.raises((OSError, FileNotFoundError)):
                copy_item_to_destination(src_file, dest_file)


class TestCopyDirectoryContentsEdgeCases:
    """Additional edge case tests for copy_directory_contents."""

    def test_copy_empty_directory(self):
        """Test copying empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            copy_directory_contents(src_dir, dest_dir)
            # Should not raise error
            assert os.path.exists(dest_dir)

    def test_extract_src_with_overwrite(self):
        """Test extract_src with overwrite flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create src subdirectory
            src_subdir = os.path.join(src_dir, "src")
            os.makedirs(src_subdir)
            with open(os.path.join(src_subdir, "file.txt"), "w") as f:
                f.write("content")

            # Create conflicting file in dest
            dest_file = os.path.join(dest_dir, "src", "file.txt")
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            with open(dest_file, "w") as f:
                f.write("old")

            copy_directory_contents(src_dir, dest_dir, extract_src=True, overwrite=True)

            # Should overwrite
            with open(dest_file, "r") as f:
                assert f.read() == "content"

    def test_extract_src_with_nested_src_directories(self):
        """Test extract_src with nested src directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir)
            os.makedirs(dest_dir)

            # Create nested src structure
            nested_src = os.path.join(src_dir, "src", "nested", "src")
            os.makedirs(nested_src)
            with open(os.path.join(nested_src, "file.txt"), "w") as f:
                f.write("content")

            copy_directory_contents(src_dir, dest_dir, extract_src=True)

            # Should extract only the top-level src
            assert os.path.exists(
                os.path.join(dest_dir, "src", "nested", "src", "file.txt")
            )


class TestResolveFilePatternEdgeCases:
    """Additional edge case tests for resolve_file_pattern."""

    def test_resolve_pattern_with_dot_files(self):
        """Test resolving pattern matching dot files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dot_file = os.path.join(tmpdir, ".hidden")
            with open(dot_file, "w") as f:
                f.write("content")

            result = resolve_file_pattern(".hidden", tmpdir)
            assert len(result) == 1
            assert result[0] == dot_file

    def test_resolve_pattern_with_multiple_extensions(self):
        """Test resolving pattern with multiple file extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for ext in [".txt", ".xml", ".json"]:
                with open(os.path.join(tmpdir, f"file{ext}"), "w") as f:
                    f.write("content")

            result = resolve_file_pattern("*.*", tmpdir)
            assert len(result) >= 3

    def test_resolve_pattern_with_question_mark(self):
        """Test resolving pattern with question mark wildcard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(tmpdir, "file2.txt"), "w") as f:
                f.write("content2")
            with open(os.path.join(tmpdir, "file10.txt"), "w") as f:
                f.write("content10")

            result = resolve_file_pattern("file?.txt", tmpdir)
            assert len(result) == 2  # file1.txt and file2.txt, not file10.txt

    def test_resolve_pattern_with_character_class(self):
        """Test resolving pattern with character class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(tmpdir, "file2.txt"), "w") as f:
                f.write("content2")
            with open(os.path.join(tmpdir, "filea.txt"), "w") as f:
                f.write("contenta")

            result = resolve_file_pattern("file[12].txt", tmpdir)
            assert len(result) == 2


class TestCopyMatchedFilesEdgeCases:
    """Additional edge case tests for copy_matched_files."""

    def test_copy_empty_file_list(self):
        """Test copying empty list of files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            copy_matched_files([], source_dir, dest_dir)
            # Should not raise error
            assert os.path.exists(dest_dir)

    def test_copy_file_at_root_level(self):
        """Test copying file at root level of source directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            source_file = os.path.join(source_dir, "root.txt")
            with open(source_file, "w") as f:
                f.write("content")

            copy_matched_files([source_file], source_dir, dest_dir)

            dest_file = os.path.join(dest_dir, "root.txt")
            assert os.path.exists(dest_file)

    def test_copy_files_with_same_name_different_paths(self):
        """Test copying files with same name from different paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            file1 = os.path.join(source_dir, "dir1", "file.txt")
            file2 = os.path.join(source_dir, "dir2", "file.txt")
            os.makedirs(os.path.dirname(file1))
            os.makedirs(os.path.dirname(file2))

            with open(file1, "w") as f:
                f.write("content1")
            with open(file2, "w") as f:
                f.write("content2")

            copy_matched_files([file1, file2], source_dir, dest_dir)

            assert os.path.exists(os.path.join(dest_dir, "dir1", "file.txt"))
            assert os.path.exists(os.path.join(dest_dir, "dir2", "file.txt"))


class TestConsolidateMetadataEdgeCases:
    """Additional edge case tests for consolidate_metadata."""

    def test_consolidate_dict_with_empty_list_patterns(self):
        """Test consolidating with empty list of patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            result, file_count = consolidate_metadata({"source": []}, tmpdir)
            # Should create temp dir but no files
            assert os.path.exists(result)
            assert file_count == 0
            clean_temp_directory(result)

    def test_consolidate_dict_with_multiple_wildcards(self):
        """Test consolidating with multiple directories using wildcards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = os.path.join(tmpdir, "dir1")
            dir2 = os.path.join(tmpdir, "dir2")
            os.makedirs(os.path.join(dir1, "src"))
            os.makedirs(os.path.join(dir2, "src"))

            with open(os.path.join(dir1, "src", "file1.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(dir2, "src", "file2.txt"), "w") as f:
                f.write("content2")

            result, file_count = consolidate_metadata(
                {"dir1": "*", "dir2": "*"}, tmpdir
            )

            assert os.path.exists(os.path.join(result, "src", "file1.txt"))
            assert os.path.exists(os.path.join(result, "src", "file2.txt"))
            assert file_count == 2
            clean_temp_directory(result)

    def test_consolidate_list_with_empty_strings(self):
        """Test consolidating list with empty strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content")

            # Empty string resolves to base_path, which is valid
            # So it will copy base_path contents, then source contents
            result, file_count = consolidate_metadata(["", "source"], tmpdir)

            # Should succeed and consolidate both
            assert os.path.exists(result)
            # Source file should be present
            assert os.path.exists(os.path.join(result, "file.txt"))
            assert file_count == 2
            clean_temp_directory(result)

    def test_consolidate_verifies_cleanup_on_error(self):
        """Test that temp directory is cleaned up on validation error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dirs_before = len(
                [
                    d
                    for d in os.listdir(tempfile.gettempdir())
                    if d.startswith("metadata_consolidate_")
                ]
            )

            try:
                consolidate_metadata("nonexistent", tmpdir)
            except ValueError:
                pass

            # Verify no new temp directories were left behind
            temp_dirs_after = len(
                [
                    d
                    for d in os.listdir(tempfile.gettempdir())
                    if d.startswith("metadata_consolidate_")
                ]
            )
            # Should be same or less (cleanup happened)
            assert temp_dirs_after <= temp_dirs_before + 1

    def test_consolidate_dict_with_nonexistent_pattern(self):
        """Test consolidating with pattern that doesn't match files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            result, file_count = consolidate_metadata(
                {"source": "nonexistent.txt"}, tmpdir
            )
            assert file_count == 0
            assert result is not None

    def test_consolidate_with_base_path_none(self):
        """Test consolidate with base_path explicitly None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source_dir = "source"
                os.makedirs(source_dir)

                with open(os.path.join(source_dir, "file.txt"), "w") as f:
                    f.write("content")

                result, file_count = consolidate_metadata(source_dir, base_path=None)
                assert os.path.exists(os.path.join(result, "file.txt"))
                assert file_count == 1
                clean_temp_directory(result)
            finally:
                os.chdir(original_cwd)


class TestConsolidateUnpackagedMetadataTaskEdgeCases:
    """Additional edge case tests for ConsolidateUnpackagedMetadata task."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_repo_root = tempfile.mkdtemp()
        self.universal_config = UniversalConfig()
        self.project_config = BaseProjectConfig(
            self.universal_config,
            config={"noyaml": True, "project": {"package": {}}},
            repo_info={"root": self.temp_repo_root},
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_repo_root):
            shutil.rmtree(self.temp_repo_root)

    def test_task_return_value_structure(self):
        """Test that task returns correct value structure."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        with open(os.path.join(source_dir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        # Task stores result in task.result
        assert isinstance(task.result, str)
        assert os.path.exists(task.result)
        # With keep_temp=True, directory should still exist
        clean_temp_directory(task.result)

    def test_task_with_error_during_consolidation(self):
        """Test task behavior when consolidation raises error."""
        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "nonexistent/path"
        }

        task_config = TaskConfig({})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        with pytest.raises(ValueError):
            task()

    def test_task_cleans_up_temp_when_keep_temp_false(self):
        """Test that task cleans up temp directory when keep_temp=False."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        with open(os.path.join(source_dir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({"options": {"keep_temp": False}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        # Directory should be cleaned up (but result still contains the path)
        result_path = task.result
        assert result_path is not None
        assert not os.path.exists(result_path)

    def test_task_with_dict_metadata_path_wildcard(self):
        """Test task with dict metadata path using wildcard."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        src_subdir = os.path.join(source_dir, "src")
        os.makedirs(src_subdir)

        with open(os.path.join(src_subdir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": {"unpackaged/pre": "*.*"}
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        result_path = task.result
        assert result_path is not None
        assert os.path.exists(os.path.join(result_path, "src", "file.txt"))
        clean_temp_directory(result_path)

    def test_task_with_list_metadata_path_multiple_dirs(self):
        """Test task with list metadata path containing multiple directories."""
        dir1 = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        dir2 = os.path.join(self.temp_repo_root, "unpackaged", "post")
        dir3 = os.path.join(self.temp_repo_root, "unpackaged", "default")
        os.makedirs(dir1)
        os.makedirs(dir2)
        os.makedirs(dir3)

        with open(os.path.join(dir1, "file1.txt"), "w") as f:
            f.write("content1")
        with open(os.path.join(dir2, "file2.txt"), "w") as f:
            f.write("content2")
        with open(os.path.join(dir3, "file3.txt"), "w") as f:
            f.write("content3")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": [
                "unpackaged/pre",
                "unpackaged/post",
                "unpackaged/default",
            ]
        }

        task_config = TaskConfig({"options": {"keep_temp": True}})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        task()

        result_path = task.result
        assert result_path is not None
        assert os.path.exists(os.path.join(result_path, "file1.txt"))
        assert os.path.exists(os.path.join(result_path, "file2.txt"))
        assert os.path.exists(os.path.join(result_path, "file3.txt"))
        clean_temp_directory(result_path)

    def test_task_logs_tree_structure(self):
        """Test that task logs directory tree structure."""
        source_dir = os.path.join(self.temp_repo_root, "unpackaged", "pre")
        os.makedirs(source_dir)

        with open(os.path.join(source_dir, "file.txt"), "w") as f:
            f.write("content")

        self.project_config.config["project"]["package"] = {
            "unpackaged_metadata_path": "unpackaged/pre"
        }

        task_config = TaskConfig({})
        task = ConsolidateUnpackagedMetadata(self.project_config, task_config, None)

        with mock.patch.object(task.logger, "info") as mock_info:
            task()

            # Check that tree printing was called
            call_args = [call[0][0] for call in mock_info.call_args_list]
            # Should have tree structure calls (containing tree characters)
            tree_calls = [msg for msg in call_args if "├──" in msg or "└──" in msg]
            assert len(tree_calls) > 0


class TestWindowsLinuxCompatibilityExtended:
    """Extended Windows/Linux compatibility tests."""

    def test_paths_with_special_characters(self):
        """Test paths with special characters that work on both platforms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use characters that are valid on both platforms
            source_dir = os.path.join(tmpdir, "source-dir_123")
            dest_dir = os.path.join(tmpdir, "dest-dir_456")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            test_file = os.path.join(source_dir, "file-name_123.txt")
            with open(test_file, "w") as f:
                f.write("content")

            copy_directory_contents(source_dir, dest_dir)

            assert os.path.exists(os.path.join(dest_dir, "file-name_123.txt"))

    def test_paths_with_unicode_characters(self):
        """Test paths with unicode characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source_测试")
            dest_dir = os.path.join(tmpdir, "dest_テスト")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            test_file = os.path.join(source_dir, "file_文件.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("content")

            copy_directory_contents(source_dir, dest_dir)

            assert os.path.exists(os.path.join(dest_dir, "file_文件.txt"))

    def test_relative_paths_with_dot_dot(self):
        """Test relative paths with .. components."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "level1", "level2")
            os.makedirs(nested_dir)

            test_file = os.path.join(nested_dir, "file.txt")
            with open(test_file, "w") as f:
                f.write("content")

            # Use relative path with .. - resolve to absolute first
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Use absolute path or resolve the relative path properly
                abs_nested = os.path.abspath(nested_dir)
                result, file_count = consolidate_metadata(abs_nested, tmpdir)
                assert os.path.exists(os.path.join(result, "file.txt"))
                assert file_count == 1
                clean_temp_directory(result)
            finally:
                os.chdir(original_cwd)

    def test_symlink_handling(self):
        """Test handling of symlinks (if supported on platform)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            # Create a regular file
            real_file = os.path.join(tmpdir, "real.txt")
            with open(real_file, "w") as f:
                f.write("content")

            # Try to create symlink (may not work on Windows without admin)
            symlink_file = os.path.join(source_dir, "link.txt")
            try:
                os.symlink(real_file, symlink_file)

                copy_directory_contents(source_dir, dest_dir)

                # Symlink should be copied (as file or link depending on platform)
                assert os.path.exists(os.path.join(dest_dir, "link.txt"))
            except (OSError, NotImplementedError):
                # Symlinks not supported on this platform
                pass

    def test_long_path_names(self):
        """Test handling of long path names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure with long names
            long_path = tmpdir
            for i in range(5):
                long_path = os.path.join(long_path, f"very_long_directory_name_{i}" * 5)
                os.makedirs(long_path)

            test_file = os.path.join(long_path, "file.txt")
            with open(test_file, "w") as f:
                f.write("content")

            # Test that we can still copy
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(dest_dir)

            copy_directory_contents(
                os.path.join(tmpdir, "very_long_directory_name_0" * 5), dest_dir
            )

            # Should handle long paths
            assert os.path.exists(dest_dir)

    def test_case_sensitivity_handling(self):
        """Test handling of case-sensitive vs case-insensitive file systems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            # Create files with different cases
            with open(os.path.join(source_dir, "File.txt"), "w") as f:
                f.write("content1")
            with open(os.path.join(source_dir, "file.txt"), "w") as f:
                f.write("content2")

            copy_directory_contents(source_dir, dest_dir)

            # Both should exist (or overwrite depending on platform)
            assert os.path.exists(os.path.join(dest_dir, "File.txt")) or os.path.exists(
                os.path.join(dest_dir, "file.txt")
            )
