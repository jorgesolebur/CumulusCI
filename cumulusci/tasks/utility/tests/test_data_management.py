import pytest

from cumulusci.core.config import (
    BaseProjectConfig,
    OrgConfig,
    TaskConfig,
    UniversalConfig,
)
from cumulusci.tasks.utility.data_management import GetFirstItemFromRecordListTask


@pytest.fixture
def a_task():
    universal_config = UniversalConfig()
    project_config = BaseProjectConfig(universal_config, config={"noyaml": True})
    org_config = OrgConfig({}, "test")

    def _a_task(options):
        task_config = TaskConfig({"options": options})
        return GetFirstItemFromRecordListTask(project_config, task_config, org_config)

    return _a_task


class TestGetFirstItemFromRecordListTask:
    def test_returns_first_item(self, a_task):
        """Tests that the task returns the first item from the 'records' list."""
        result_input = {
            "records": [
                {"Id": "001", "Name": "Test Account"},
                {"Id": "002", "Name": "Another Account"},
            ]
        }
        task = a_task({"result": result_input})
        task()
        assert task.return_values == {"Id": "001", "Name": "Test Account"}

    def test_empty_record_list(self, a_task):
        """Tests that an IndexError is raised for an empty 'records' list."""
        result_input = {"records": []}
        task = a_task({"result": result_input})
        with pytest.raises(IndexError):
            task()
