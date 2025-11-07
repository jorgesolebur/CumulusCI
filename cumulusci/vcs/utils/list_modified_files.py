"""Utility functions and task for working with git modified files."""

import os
import subprocess
from typing import Optional, Set

from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import CCIOptions, Field, ListOfStringsOption


class ListModifiedFiles(BaseTask):
    """Task to list modified files in a git repository.

    This task compares the current working directory against a base reference
    (branch, tag, or commit) and lists all modified files, optionally filtered
    to package directories.
    """

    class Options(CCIOptions):
        base_ref: Optional[str] = Field(
            None,
            description="Git reference (branch, tag, or commit) to compare against. "
            "If not set, uses the default branch of the repository.",
        )
        file_extensions: Optional[ListOfStringsOption] = Field(
            None,
            description="List of file extensions to extract. If not set, all file extensions are extracted. Example: ['cls', 'flow', 'trigger']",
        )
        directories: ListOfStringsOption = Field(
            ["force-app", "src"],
            description="List of directories to extract. If not set, only the default package directory is extracted. Example: ['force-app', 'src']",
        )

    parsed_options: Options

    def _init_options(self, kwargs):
        super(ListModifiedFiles, self)._init_options(kwargs)

        if self.parsed_options.base_ref is None:
            self.parsed_options.base_ref = (
                self.project_config.project__git__default_branch or "main"
            )

    def _run_task(self):
        """Run the task to list modified files."""
        self.return_values = {
            "files": set(),
            "file_names": set(),
        }

        # Check if the current base folder has git
        if self.project_config.get_repo() is None:
            self.logger.info("No git repository found.")
            return

        # Get changed files
        changed_files = self._get_git_changed_files()

        if changed_files is None:
            self.logger.warning(
                f"Could not determine git changes against {self.parsed_options.base_ref}."
            )
            return

        if not changed_files:
            self.logger.info("No files changed.")
            return

        # Filter to directories if requested
        changed_files = self._filter_package_changed_files(changed_files)

        if not changed_files:
            self.logger.info(
                f"No changed files found in directories: {', '.join(self.parsed_options.directories)}."
            )
            return

        self.return_values["files"] = sorted(changed_files)

        # Extract file names if requested
        file_names = set()
        if self.parsed_options.file_extensions is not None:
            file_names = self._extract_file_names_from_files(changed_files)
            if file_names:
                self.logger.info(
                    f"Found {len(file_names)} affected file(s): {', '.join(sorted(file_names))}"
                )
                self.return_values["file_names"] = file_names
            else:
                self.logger.info("No file names found in changed files.")

        # Log file list if not too many
        if len(changed_files) > 0 and len(changed_files) <= 20:
            self.logger.info("Changed files:")
            for file_path in changed_files:
                self.logger.info(f"  {file_path}")
        else:
            self.logger.info(f"  ... and {len(changed_files) - 20} more files")

        if len(file_names) > 0 and len(file_names) <= 20:
            self.logger.info("Selected file names:")
            for file_name in file_names:
                self.logger.info(f"  {file_name}")
        else:
            self.logger.info(f"  ... and {len(file_names) - 20} more file names")

    def _get_git_changed_files(self) -> Optional[Set[str]]:
        """Get list of changed files using git diff.
        Returns:
            Set of changed file paths, or None if git command failed
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", self.parsed_options.base_ref],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.logger.warning(
                    f"Git diff failed with return code {result.returncode}: {result.stderr}"
                )
                return None

            return set([f.strip() for f in result.stdout.splitlines() if f.strip()])

        except FileNotFoundError:
            self.logger.warning(
                "Git command not found. Cannot determine changed files."
            )
            return set()
        except Exception as e:
            self.logger.warning(f"Error running git diff: {str(e)}")
            return set()

    def _filter_package_changed_files(self, changed_files: Set[str]) -> Set[str]:
        """Filter changed files to only include those in the package directories."""
        package_dir = os.path.basename(
            os.path.normpath(self.project_config.default_package_path)
        )

        if package_dir not in self.parsed_options.directories:
            self.parsed_options.directories.append(package_dir)

        filtered_files = set()
        for file_path in changed_files:
            # Check if file is in any of the package directories
            for pkg_dir in self.parsed_options.directories:
                if file_path.startswith(pkg_dir + "/") or file_path.startswith(
                    pkg_dir + "\\"
                ):
                    filtered_files.add(file_path)
                    break

        return set(filtered_files)

    def _extract_file_names_from_files(self, changed_files: Set[str]) -> Set[str]:
        """Extract file names from changed file paths based on specified extensions.

        Args:
            changed_files: List of changed file paths

        Returns:
            Set of file names found in changed files matching the specified extensions
        """
        file_names = set()

        for file_path in changed_files:
            # Check if file path ends with any of the specified extensions
            # Handle both "cls" and ".cls" formats
            matched_extension = None
            for ext in self.parsed_options.file_extensions:
                # Normalize extension to have a dot prefix
                normalized_ext = ext if ext.startswith(".") else f".{ext}"
                if file_path.endswith(normalized_ext):
                    matched_extension = normalized_ext
                    break

            if matched_extension:
                # Extract file name from path
                # Examples: force-app/main/default/classes/MyClass.cls -> MyClass
                #          src/classes/MyClass.cls -> MyClass
                file_name = os.path.basename(file_path)
                file_name = file_name.replace(matched_extension, "")
                if file_name:
                    file_names.add(file_name)

        return file_names
