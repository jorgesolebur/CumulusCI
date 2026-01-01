import os
import time
from pathlib import Path
from typing import Dict, Optional

import yaml

from cumulusci.cli.utils import timestamp_file
from cumulusci.core.exceptions import CumulusCIException, TaskOptionsError
from cumulusci.core.tasks import BaseTask
from cumulusci.utils import download_extract_vcs_from_repo, filter_namelist
from cumulusci.utils.options import (
    CCIOptions,
    CCIOptionType,
    Field,
    ListOfStringsOption,
    parse_list_of_pairs_dict_arg,
)
from cumulusci.vcs.bootstrap import get_repo_from_url
from cumulusci.vcs.models import AbstractRepo
from cumulusci.vcs.utils import get_ref_from_options


class DownloadExtractRenamesOption(CCIOptionType):
    """Parses renames option from string, dict, or list of dicts format.

    Supports:
    - String format: "src/old.py:src/new.py,docs/:documentation/"
    - Dict format: {"src/old.py": "src/new.py", "docs/": "documentation/"}
    - List of dicts format: [{"local": "src/old.py", "target": "src/new.py"}, ...]
    """

    @classmethod
    def from_str(cls, v) -> Dict[str, str]:
        """Parse string format like "key:value,key2:value2" """
        return parse_list_of_pairs_dict_arg(v)

    @classmethod
    def validate(cls, v):
        """Validate and convert renames from various input formats."""
        if v is None:
            return {}

        # Handle string format (delegates to from_str)
        if isinstance(v, str):
            return super().validate(v)

        # Handle dict format - return as-is
        if isinstance(v, dict):
            return v

        # Handle list of dicts format (for backward compatibility)
        if isinstance(v, list):
            if not v:  # Empty list
                return {}

            # Validate all items are dicts with correct keys
            is_list_of_dicts = all(isinstance(pair, dict) for pair in v)
            dicts_have_correct_keys = is_list_of_dicts and all(
                {"local", "target"} == pair.keys() for pair in v
            )

            ERROR_MSG = "Renamed paths must be a list of dicts with `local:` and `target:` keys."
            if not dicts_have_correct_keys:
                raise TaskOptionsError(ERROR_MSG)

            # Convert list of dicts to flat dict
            local_to_target_paths = {}
            for rename in v:
                local_path = rename.get("local")
                target_path = rename.get("target")

                if local_path and target_path:
                    local_to_target_paths[local_path] = target_path
                else:
                    raise TaskOptionsError(ERROR_MSG)

            return local_to_target_paths

        # Invalid type
        raise TaskOptionsError(
            f"Renames must be a string, dict, or list of dicts, got {type(v).__name__}"
        )


class DownloadExtract(BaseTask):
    task_docs = """A task to download and extract files and folders from a Git repository.
    Will download the repository and extract it to a specified directory.
    """

    class Options(CCIOptions):
        repo_url: str = Field(..., description="The url to the repo")
        target_directory: str = Field(
            ...,
            description=(
                "The directory to extract the repo contents to. "
                "If not set, contents will be extracted to the current directory. "
                "If set, it must be a relative path from the project root or an absolute path."
            ),
        )
        sub_folder: Optional[str] = Field(
            None, description="The subfolder directory to download from the repo."
        )
        branch: Optional[str] = Field(
            None,
            description=(
                "The branch to fetch from the repo. "
                "If 'ref' or 'tag_name' is not set, the default branch will be set."
            ),
        )
        tag_name: Optional[str] = Field(
            None,
            description=(
                "The name of the tag that should be downloaded. "
                "Values of 'latest' and 'latest_beta' are also allowed. "
                "Not required if 'branch' is set. Required if 'ref' is not set."
            ),
        )
        ref: Optional[str] = Field(
            None,
            description=(
                "The git reference to download. Takes precedence over 'tag_name' and 'branch'. "
                "Required if 'tag_name' or 'branch' is not set."
            ),
        )
        include: Optional[ListOfStringsOption] = Field(
            None,
            description=(
                "A list of paths from repo root to include. "
                "Directories must end with a trailing slash."
            ),
        )
        renames: Optional[DownloadExtractRenamesOption] = Field(
            {},
            description=(
                "A list of paths to rename in the target repo, "
                "given as `local:` `target:` pairs."
            ),
        )
        force: bool = Field(False, description="Force Download files in the repo.")

    parsed_options: Options

    def _init_repo(self):
        self.repo: AbstractRepo = get_repo_from_url(
            self.project_config, self.parsed_options.repo_url
        )
        self._set_ref()
        self.commit = self.repo.get_ref(self.ref).sha

    def _run_task(self):
        self._set_target_directory()

        if not self._check_latest_commit():
            self.logger.info(
                f"Skipping download, no new changes in {self.parsed_options.repo_url} since last run."
            )
            return

        self.logger.info(
            f"{'Force ' if self.parsed_options.force else ''}Downloading files from {self.parsed_options.repo_url}."
        )

        target = Path(os.path.join(self.parsed_options.target_directory))
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)

        self._download_repo_and_extract(target)
        self._rename_files(target)

        with timestamp_file(self.parsed_options.target_directory) as f:
            yaml.dump({"commit": self.commit, "timestamp": time.time()}, f)

    def _set_ref(self):
        if self.parsed_options.branch:
            branch = self.parsed_options.branch
            self.ref = f"heads/{branch}"
            return

        try:
            # Pass parsed_options directly - Pydantic models support dict-like access
            self.ref = get_ref_from_options(self.project_config, self.parsed_options)
        except CumulusCIException:
            # If no ref, tag_name or branch is set, default to the repo's default branch
            self.ref = f"heads/{self.repo.default_branch}"

    def _download_repo_and_extract(self, path):
        zf = download_extract_vcs_from_repo(
            self.repo,
            subfolder=self.parsed_options.sub_folder,
            ref=self.commit,
        )

        included_members = zf.namelist()
        if self.parsed_options.include:
            included_members = filter_namelist(
                includes=self.parsed_options.include, namelist=zf.namelist()
            )
        zf.extractall(path=path, members=included_members)
        zf.close()

    def _rename_files(self, zip_dir):
        # renames are already processed by DownloadExtractRenamesOption
        if not self.parsed_options.renames:
            return

        for local_name, target_name in self.parsed_options.renames.items():
            local_path = Path(zip_dir, local_name)
            if local_path.exists():
                target_path = Path(zip_dir, target_name)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.replace(target_path)

    def _set_target_directory(self):
        """
        Sets the target directory where the repo contents will be extracted.
        If not set, defaults to the current directory.
        """
        # Check if self.parsed_options.target_directory is absolute or relative path.
        target_directory = self.parsed_options.target_directory
        if not os.path.isabs(target_directory):
            # If it's a relative path, make it absolute based on project root
            target_directory = os.path.join(
                self.project_config.repo_root, target_directory
            )
        self.parsed_options.target_directory = target_directory

    def _check_latest_commit(self):
        """checks for the latest commit in repo, max once per hour"""
        if self.parsed_options.force:
            self._init_repo()
            return True

        check = True

        timestamp = 0
        commit = ""
        if os.path.isfile(f"{self.parsed_options.target_directory}/cumulus_timestamp"):
            with timestamp_file(self.parsed_options.target_directory) as f:
                loaded_data = yaml.safe_load(f)
                timestamp = loaded_data.get("timestamp", 0)
                commit = loaded_data.get("commit", "")

        delta = time.time() - timestamp
        check = delta > 3600

        if not check:
            return False

        self._init_repo()
        if self.commit != commit:
            return True

        return False
