from typing import Any

from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import CCIOptions, Field


class GetFirstItemFromRecordListTask(BaseTask):
    class Options(CCIOptions):
        result: dict[str, Any] = Field(
            None, description="The result from SF CLI operations."
        )

    parsed_options: Options

    def _run_task(self):
        self.return_values = self.parsed_options.result["records"][0]
