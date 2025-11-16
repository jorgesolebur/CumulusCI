import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

from pydantic.v1 import BaseModel, validator

from cumulusci.core.config import BaseProjectConfig, OrgConfig, TaskConfig
from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import CCIOptions, Field
from cumulusci.vcs.bootstrap import get_repo_from_url


class EnvManagementOption(CCIOptions):
    name: str = Field(
        ...,
        description="The name of the environment variable to get the value from the environment",
    )
    default: Any = Field(
        default=None,
        description="The default value of the environment variable. Defaults to None",
    )
    datatype: str = Field(
        default="string",
        description="The datatype of the environment variable. Defaults to string. Valid values are string, bool, int, float, date, list, dict, path, directory, filename, vcs_repo",
    )
    set: bool = Field(
        default=False,
        description="If True, sets the value of the environment variable if it is not already set. Defaults to False",
    )

    @validator("datatype")
    def validate_datatype(cls, v):
        if v not in [
            "string",
            "bool",
            "int",
            "float",
            "date",
            "list",
            "dict",
            "path",
            "directory",
            "filename",
            "vcs_repo",
        ]:
            raise ValueError(f"Invalid datatype: {v}")
        return v

    def formated_value(
        self,
        task_values: dict[str, Any],
        project_config: Optional[BaseProjectConfig],
        org_config: Optional[OrgConfig],
        logger: logging.Logger,
    ) -> None:
        value = os.getenv(self.name, self.default)
        datatype = self.datatype or "string"

        try:
            if self.name not in task_values:
                match datatype:
                    case "string":
                        task_values[self.name] = str(value)
                    case "bool":
                        v = DummyValidatorModel(b=value).b
                        task_values[self.name] = v
                    case "int":
                        v = DummyValidatorModel(i=value).i
                        task_values[self.name] = v
                    case "float":
                        v = DummyValidatorModel(f=value).f
                        task_values[self.name] = v
                    case "date":
                        v = DummyValidatorModel(d=date.fromisoformat(str(value))).d
                        task_values[self.name] = v
                    case "list":
                        v = value if isinstance(value, list) else value.split(",")
                        task_values[self.name] = v
                    case "dict":
                        v = value if isinstance(value, dict) else json.loads(str(value))
                        task_values[self.name] = v
                    case "path":
                        v = Path(str(value))
                        task_values[self.name] = v.absolute()
                    case "directory":
                        v = Path(str(value)).parent.absolute()
                        task_values[self.name] = v.absolute()
                    case "filename":
                        v = Path(str(value)).name
                        task_values[self.name] = v
                    case "vcs_repo":
                        task_config = TaskConfig(
                            {"options": {"url": self.default, "name": self.name}}
                        )
                        task = VcsRemoteBranch(project_config, task_config, org_config)
                        result = task()
                        task_values[self.name] = result["url"]
                        task_values[f"{self.name}_BRANCH"] = result["branch"]
                    case _:
                        raise ValueError(f"Invalid datatype: {datatype}")
            else:
                logger.info(f"Variable {self.name} already set. Skipping.")

        except Exception as e:
            raise ValueError(
                f"Formatting Error: {value} for datatype: {datatype} - {e}"
            )

        if self.set:
            os.environ[self.name] = str(task_values[self.name])

        if self.set and self.datatype == "vcs_repo":
            os.environ[f"{self.name}_BRANCH"] = str(task_values[f"{self.name}_BRANCH"])


class DummyValidatorModel(BaseModel):
    b: Optional[bool]
    i: Optional[int]
    f: Optional[float]
    d: Optional[date]


class EnvManagement(BaseTask):
    class Options(CCIOptions):
        envs: List[EnvManagementOption] = Field(
            default=[],
            description="A list of environment variables definitions.",
        )

    parsed_options: Options

    def _run_task(self):
        self.return_values = {}

        for env_option in self.parsed_options.envs:
            env_option.formated_value(
                self.return_values, self.project_config, self.org_config, self.logger
            )

        return self.return_values


class VcsRemoteBranch(BaseTask):
    class Options(CCIOptions):
        url: str = Field(
            ...,
            description="Gets if the remote branch name exist with the same name in the remote repository.",
        )
        name: str = Field(
            ...,
            description="The name of the environment variable.",
        )

    parsed_options: Options

    def _run_task(self):
        self.return_values = {}

        # Get current branch name. Based on Local Git Branch if not available from Environment Variable
        local_branch = os.getenv(
            f"{self.parsed_options.name}_BRANCH", self.project_config.repo_branch
        )

        # Get repository URL from Environment Variable
        self.return_values["url"] = os.getenv(
            self.parsed_options.name, self.parsed_options.url
        )

        repo = get_repo_from_url(self.project_config, self.return_values["url"])

        try:
            branch = repo.branch(local_branch)
            self.logger.info(
                f"Branch {local_branch} found in repository {self.return_values['url']}."
            )
            self.return_values["branch"] = branch.name
        except Exception:
            self.logger.warning(
                f"Branch {local_branch} not found in repository {self.return_values['url']}. Using default branch {repo.default_branch}"
            )
            self.return_values["branch"] = repo.default_branch

        return self.return_values
