#!/usr/bin/env python3
"""
Standalone script to test directory merging and copying logic for unpackaged metadata.

This script consolidates metadata from multiple directories into a temporary directory,
merging overlapping directory structures.
"""

import glob
import os
import shutil
import tempfile
from logging import Logger
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import CCIOptions, Field

IGNORE_FILES = [".gitkeep", ".DS_Store"]


def merge_directory_contents(src_dir: str, dest_dir: str, overwrite: bool = False):
    """
    Recursively merge contents from src_dir into dest_dir.
    If a file exists in both, the source file overwrites the destination.
    """
    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dest_item = os.path.join(dest_dir, item)

        if os.path.isdir(src_item):
            if os.path.exists(dest_item) and os.path.isdir(dest_item):
                # Recursively merge subdirectories
                merge_directory_contents(src_item, dest_item)
            else:
                # Copy directory if it doesn't exist or replace if it's a file
                if os.path.exists(dest_item) and overwrite:
                    if os.path.isdir(dest_item):
                        shutil.rmtree(dest_item)
                    else:
                        os.remove(dest_item)
                shutil.copytree(src_item, dest_item)
        else:
            # Copy file, overwriting if it exists
            if os.path.exists(dest_item) and os.path.isdir(dest_item) and overwrite:
                shutil.rmtree(dest_item)
            shutil.copy2(src_item, dest_item)


def copy_item_to_destination(source_item: str, dest_item: str, overwrite: bool = False):
    """
    Copy a file or directory to destination, merging if destination exists.

    Args:
        source_item: Source file or directory path
        dest_item: Destination file or directory path
    """
    if os.path.isdir(source_item):
        if os.path.exists(dest_item) and os.path.isdir(dest_item):
            merge_directory_contents(source_item, dest_item, overwrite)
        else:
            # Remove destination if it exists (file or wrong type)
            if os.path.exists(dest_item):
                if os.path.isdir(dest_item) and overwrite:
                    shutil.rmtree(dest_item)
                else:
                    os.remove(dest_item)
            shutil.copytree(source_item, dest_item)
    else:
        # Remove destination if it's a directory
        if os.path.exists(dest_item) and os.path.isdir(dest_item) and overwrite:
            shutil.rmtree(dest_item)
        shutil.copy2(source_item, dest_item)


def copy_directory_contents(
    source_dir: str, dest_dir: str, extract_src: bool = False, overwrite: bool = False
):
    """
    Copy all contents from source_dir to dest_dir.

    Args:
        source_dir: Source directory path
        dest_dir: Destination directory path
        extract_src: If True and source_dir contains 'src', copy src contents to dest_dir/src
    """
    if extract_src:
        src_path = os.path.join(source_dir, "src")
        if os.path.exists(src_path) and os.path.isdir(src_path):
            # Copy src directory contents directly to dest_dir/src
            temp_src_dir = os.path.join(dest_dir, "src")
            os.makedirs(temp_src_dir, exist_ok=True)
            for item in os.listdir(src_path):
                source_item = os.path.join(src_path, item)
                dest_item = os.path.join(temp_src_dir, item)
                copy_item_to_destination(source_item, dest_item, overwrite)
            return

    # No src directory or extract_src is False, copy everything directly to dest_dir
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        dest_item = os.path.join(dest_dir, item)
        copy_item_to_destination(source_item, dest_item, overwrite)


def resolve_file_pattern(pattern: str, source_dir: str) -> List[str]:
    """
    Resolve a file pattern to a list of matching files.

    Args:
        pattern: Glob pattern or file path
        source_dir: Base directory for resolving relative patterns

    Returns:
        List of matched file paths

    Raises:
        ValueError: If pattern doesn't match any files
    """
    pattern_path = os.path.join(source_dir, pattern)
    matched_files = glob.glob(pattern_path, recursive=True)

    if not matched_files:
        # If no glob match, treat as literal file path
        if os.path.exists(pattern_path):
            matched_files = [pattern_path]
        else:
            matched_files = []

    # Normalize paths to use OS-native separators (fixes Windows path separator issues)
    return [os.path.normpath(path) for path in matched_files]


def copy_matched_files(matched_files: List[str], source_dir: str, dest_dir: str):
    """
    Copy matched files to destination, preserving relative structure.

    Args:
        matched_files: List of file paths to copy
        source_dir: Source base directory for calculating relative paths
        dest_dir: Destination base directory
    """
    for matched_file in matched_files:
        # Calculate relative path from source_dir
        rel_path = os.path.relpath(matched_file, source_dir)
        dest_file = os.path.join(dest_dir, rel_path)
        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
        copy_item_to_destination(matched_file, dest_file)


def clean_temp_directory(temp_dir: str):
    """
    Clean up a temporary directory.
    Args:
        temp_dir: Path to the temporary directory
    """
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def validate_directory(path: str, path_name: str = "path"):
    """
    Validate that a path exists and is a directory.

    Args:
        path: Path to validate
        path_name: Name of the path for error messages

    Raises:
        ValueError: If path doesn't exist or is not a directory
    """
    if not os.path.exists(path):
        raise ValueError(f"{path_name} does not exist: {path}")
    if not os.path.isdir(path):
        raise ValueError(f"{path_name} is not a directory: {path}")


def consolidate_metadata(
    metadata_path: Union[str, List[str], Dict[str, Union[str, List[str]]]],
    base_path: str = None,
    logger: Optional[Logger] = None,
) -> Tuple[str, int]:
    """
    Consolidate metadata from various sources into a temporary directory.

    Args:
        metadata_path: Can be:
            1. string: path to a directory (relative to base_path)
            2. list of strings: list of paths to directories
            3. dict: dict with keys as directory names and values as file patterns
        base_path: Base path for resolving relative paths. Defaults to current directory.

    Returns:
        Path to the temporary directory containing consolidated metadata

    unpackaged_metadata_path supported formats:
    # 1. string: path to a directory
    # Example:
    # unpackaged_metadata_path: "unpackaged/pre"

    # 2. list of strings: list of paths to directories
    # Example:
    # unpackaged_metadata_path:
    #   - "unpackaged/pre"
    #   - "unpackaged/post"

    # 3. dict: dict with keys as directory names and values as relative filepaths to the directory
    # Example:
    # unpackaged_metadata_path:
    #   "unpackaged/pre": "*.*"
    #   "unpackaged/post": "src/objects/Account/fields/Name.field-meta.xml"
    #   "unpackaged/default":
    #     - "src/objects/Account/fields/Name.field-meta.xml"
    #     - "src/objects/Account/fields/Description.field-meta.xml"
    """
    if base_path is None:
        base_path = os.getcwd()

    # Create a temporary directory to consolidate all metadata
    temp_dir = tempfile.mkdtemp(prefix="metadata_consolidate_")

    try:
        if isinstance(metadata_path, str):
            # Format 1: Single directory path
            source_path = (
                os.path.join(base_path, metadata_path)
                if not os.path.isabs(metadata_path)
                else metadata_path
            )
            validate_directory(source_path, "Unpackaged metadata path")

            # Copy entire directory to temp
            copy_directory_contents(source_path, temp_dir)

        elif isinstance(metadata_path, list):
            # Format 2: List of directory paths
            for path_item in metadata_path:
                source_path = (
                    os.path.join(base_path, path_item)
                    if not os.path.isabs(path_item)
                    else path_item
                )
                validate_directory(source_path, "Unpackaged metadata path")

                # Copy all contents directly to temp folder, merging directories
                copy_directory_contents(source_path, temp_dir)

        elif isinstance(metadata_path, dict):
            # Format 3: Dict with directory keys and file pattern/value lists
            # For dict format, merge all src directories directly into temp_dir/src
            for dir_key, file_patterns in metadata_path.items():
                source_dir = (
                    os.path.join(base_path, dir_key)
                    if not os.path.isabs(dir_key)
                    else dir_key
                )
                validate_directory(source_dir, "Unpackaged metadata directory")

                # Handle different value types
                if isinstance(file_patterns, str):
                    # Single pattern or file path
                    if file_patterns == "*.*" or file_patterns == "*":
                        # Copy all files from source directory, extracting src if present
                        copy_directory_contents(source_dir, temp_dir, extract_src=True)
                    else:
                        # Treat as glob pattern or specific file path
                        matched_files = resolve_file_pattern(file_patterns, source_dir)
                        if logger and not matched_files:
                            logger.warning(
                                f"File pattern does not match any files: {file_patterns}"
                            )
                            continue
                        copy_matched_files(matched_files, source_dir, temp_dir)

                elif isinstance(file_patterns, list):
                    # List of file paths/patterns
                    for pattern in file_patterns:
                        matched_files = resolve_file_pattern(pattern, source_dir)
                        if logger and not matched_files:
                            logger.warning(
                                f"File pattern does not match any files: {pattern}"
                            )
                            continue
                        copy_matched_files(matched_files, source_dir, temp_dir)
                else:
                    raise ValueError(
                        f"Invalid file pattern type for directory {dir_key}: {type(file_patterns)}"
                    )
        else:
            raise ValueError(f"Invalid unpackaged metadata path: {metadata_path}")

        # Count the files in the final_metadata_path and log the count, ignore .gitkeep files
        file_count = len(
            [
                p
                for p in Path(temp_dir).rglob("*")
                if p.name not in IGNORE_FILES and p.is_file()
            ]
        )
        if logger:
            logger.info(
                f"Found {file_count} files in the consolidated metadata path, ignoring .gitkeep files: {temp_dir}"
            )

        return temp_dir, file_count

    except Exception:
        # Clean up temp directory on error
        clean_temp_directory(temp_dir)
        raise


def print_directory_tree(
    path: str,
    prefix: str = "",
    max_depth: int = 10,
    current_depth: int = 0,
    logger: Logger = None,
):
    """Print a directory tree structure."""
    if current_depth >= max_depth:
        return

    try:
        items = sorted(os.listdir(path))
        for i, item in enumerate(items):
            item_path = os.path.join(path, item)
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            if logger:
                logger.info(f"{prefix}{current_prefix}{item}")
            else:
                print(f"{prefix}{current_prefix}{item}")

            if os.path.isdir(item_path):
                extension = "    " if is_last else "│   "
                print_directory_tree(
                    item_path, prefix + extension, max_depth, current_depth + 1, logger
                )
    except PermissionError:
        pass


"""
CumulusCI task to consolidate unpackaged metadata from multiple sources.

This task reads the unpackaged_metadata_path configuration from project config
and consolidates all metadata into a single temporary directory.
"""


class ConsolidateUnpackagedMetadata(BaseTask):
    """Consolidate unpackaged metadata from multiple sources into a single directory.

    This task reads the `project__package__unpackaged_metadata_path` configuration
    and consolidates all metadata according to the specified format (string, list, or dict).

    The consolidated directory path is returned in `return_values['path']`.
    """

    class Options(CCIOptions):
        base_path: str = Field(
            None,
            description="Base path for resolving relative paths. Defaults to repo_root.",
        )
        keep_temp: bool = Field(
            False, description="Keep temporary directory after execution."
        )

    parsed_options: Options

    def _run_task(self):
        """Execute the consolidation task."""
        # Get unpackaged_metadata_path from project config
        metadata_path = self.project_config.project__package__unpackaged_metadata_path

        if not metadata_path:
            self.logger.warning(
                "No unpackaged_metadata_path configured. Skipping consolidation."
            )
            self.return_values["path"] = None
            return

        # Determine base path
        base_path = self.parsed_options.base_path
        if base_path is None:
            base_path = self.project_config.repo_root

        self.logger.info(f"Consolidating unpackaged metadata from: {metadata_path}")
        self.logger.info(f"Using base path: {base_path}")

        # Consolidate metadata
        consolidated_path, _ = consolidate_metadata(
            metadata_path, base_path, logger=self.logger
        )
        print_directory_tree(consolidated_path, logger=self.logger)

        if not self.parsed_options.keep_temp:
            clean_temp_directory(consolidated_path)

        return consolidated_path
