import os
import shutil
from pathlib import Path

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import CCIOptions, Field


class DirectoryRecreator(BaseTask):
    class Options(CCIOptions):
        path: Path = Field(..., description="Path to the directory to recreate")

    parsed_options: Options

    def _init_options(self, kwargs):
        super()._init_options(kwargs)

        if os.path.isfile(self.parsed_options.path):
            raise TaskOptionsError(f"Path {self.parsed_options.path} is a file")

    def _run_task(self):
        created = "created"
        if os.path.exists(self.parsed_options.path):
            shutil.rmtree(self.parsed_options.path)
            created = "removed and created"

        os.makedirs(self.parsed_options.path, exist_ok=True)

        self.logger.info(f"Directory {self.parsed_options.path} {created}.")
