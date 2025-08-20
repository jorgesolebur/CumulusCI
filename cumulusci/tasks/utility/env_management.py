import json
import os
from datetime import date
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, validator

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
        description="The datatype of the environment variable. Defaults to string. Valid values are string, bool, int, float, date, list, dict, path, directory, filename, vcs_branch",
    )
    set: bool = Field(
        default=False,
        description="If True, sets the value of the environment variable if it is not already set. Defaults to False",
    )
    url: str = Field(
        default="",
        description="The url of the repository to get the branch value from, Applicable only for vcs_branch datatype. Defaults to empty string",
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
            "vcs_branch",
        ]:
            raise ValueError(f"Invalid datatype: {v}")
        return v

    def formated_value(
        self,
        project_config: Optional[BaseProjectConfig],
        org_config: Optional[OrgConfig],
    ) -> tuple[Any, str]:
        value = os.getenv(self.name, self.default)
        datatype = self.datatype or "string"

        try:
            match datatype:
                case "string":
                    return str(value), str(value)
                case "bool":
                    v = DummyValidatorModel(b=value).b
                    return v, str(v)
                case "int":
                    v = DummyValidatorModel(i=value).i
                    return v, str(v)
                case "float":
                    v = DummyValidatorModel(f=value).f
                    return v, str(v)
                case "date":
                    v = DummyValidatorModel(d=date.fromisoformat(str(value))).d
                    return v, str(v)
                case "list":
                    v = value if isinstance(value, list) else value.split(",")
                    return v, str(v)
                case "dict":
                    v = value if isinstance(value, dict) else json.loads(str(value))
                    return v, str(v)
                case "path":
                    v = Path(str(value))
                    return v.absolute(), str(v.absolute())
                case "directory":
                    v = Path(str(value)).parent.absolute()
                    return v, str(v.absolute())
                case "filename":
                    v = Path(str(value)).name
                    return v, str(v)
                case "vcs_branch":
                    task_config = TaskConfig({"options": {"url": self.url}})
                    task = VcsRemoteBranch(project_config, task_config, org_config)
                    result = task()
                    return result["remote_branch"], str(result["remote_branch"])
                case _:
                    raise ValueError(f"Invalid datatype: {datatype}")
        except Exception as e:
            raise ValueError(
                f"Formatting Error: {value} for datatype: {datatype} - {e}"
            )


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
            self.return_values[env_option.name], str_value = env_option.formated_value(
                self.project_config, self.org_config
            )
            if env_option.set and env_option.name not in os.environ:
                os.environ[env_option.name] = str_value

        return self.return_values


class VcsRemoteBranch(BaseTask):
    class Options(CCIOptions):
        url: str = Field(
            ...,
            description="Gets if the remote branch name exist with the same name in the remote repository.",
        )

    parsed_options: Options

    def _run_task(self):
        self.return_values = {}
        # Get current branch name.
        local_branch = self.project_config.repo_branch
        repo = get_repo_from_url(self.project_config, self.parsed_options.url)

        try:
            branch = repo.branch(local_branch)
            self.return_values["remote_branch"] = branch.name
        except Exception:
            self.return_values["remote_branch"] = repo.default_branch

        return self.return_values
