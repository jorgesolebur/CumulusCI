from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.base_source_control_task import BaseSourceControlTask
from cumulusci.utils.options import CCIOptions, Field


class CreatePackageDataFromCommitStatus(BaseSourceControlTask):
    class Options(CCIOptions):
        state: str = Field(description="sha of the commit")
        context: str = Field(description="Name of the commit status context")
        commit_id: str = Field(description="sha of the commit", default=None)
        description: str = Field(
            description="Description of the commit status", default=None
        )
        target_url: str = Field(
            description="URL to associate with the commit status", default=None
        )

    parsed_options: Options

    def _run_task(self):
        repo = self.get_repo()
        commit_sha = (
            self.parsed_options.commit_id or self.project_config.repo_commit or ""
        )

        if not commit_sha:
            raise TaskOptionsError(
                "Commit not found. Please provide a valid commit ID."
            )

        commit = repo.create_commit_status(
            commit_sha,
            state=self.parsed_options.state,
            context=self.parsed_options.context,
            description=self.parsed_options.description,
            target_url=self.parsed_options.target_url,
        )

        self.return_values = {"commit_id": commit.sha}

        self.logger.info(
            f"Commit status created for commit {commit_sha} with state {self.parsed_options.state}"
        )
