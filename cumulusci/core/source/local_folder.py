import os
from pathlib import Path

from cumulusci.utils.yaml.cumulusci_yml import LocalFolderSourceModel


class LocalFolderSource:
    def __init__(self, project_config, spec: LocalFolderSourceModel):
        self.project_config = project_config
        self.spec = spec
        self.path = spec.path
        self.location = self.path

    def __repr__(self):
        return f"<LocalFolderSource {str(self)}>"

    def __str__(self):
        return f"Local folder: {self.path}"

    def __hash__(self):
        return hash((self.path,))

    def fetch(self):
        """Construct a project config referencing the specified path."""
        root = os.path.realpath(self.path)
        # Pass explicit cache_dir so subproject doesn't depend on parent's
        # repo_root (which may be None in CI/meta-project contexts)
        cache_dir = Path(root) / ".cci"
        project_config = self.project_config.construct_subproject_config(
            repo_info={"root": root},
            cache_dir=cache_dir,
        )
        return project_config

    @property
    def frozenspec(self):
        raise NotImplementedError("Cannot construct frozenspec for local folder")

    @property
    def allow_remote_code(self) -> bool:
        return bool(self.spec.allow_remote_code)
