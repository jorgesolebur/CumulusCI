import cumulusci.core.azure_devops as scm
from cumulusci.core.tasks import BaseScmTask


class BaseAzureTask(BaseScmTask):
    def _init_task(self):
        super()._init_task()

        # Set azure variables
        self.azure_config = self.project_config.keychain.get_service("azure_devops")
        self.azure_connection = scm.get_azure_api_conntection(self.azure_config)
        self.azure_core_client = self.azure_connection.clients.get_core_client()
        self.azure_git_client = self.azure_connection.clients.get_git_client()
        scm.client = self.azure_git_client

    def init_merge_repo_options(self):
        self.options["completion_opts_delete_source_branch"] = (False,)
        self.options["completion_opts_merge_strategy"] = (
            "squash",
        )  # 'noFastForward', 'rebase', 'rebaseMerge', etc.
        self.options["completion_opts_bypass_policy"] = (False,)
        self.options["completion_opts_bypass_reason"] = (
            "Automated bypass for CI/CD pipeline",
        )

    def get_repo(self):
        if scm.repo is not None:
            return scm.repo

        scm.repo = scm.get_repo(
            self.project_config.repo_name, self.project_config.repo_project_name
        )
        scm.project = scm.repo.project

        return scm.repo

    def create_tag(self):
        self.get_repo()

        src_tag = scm.get_tag_by_name(self.options["src_tag"])
        tag = scm.clone_tag(src_tag, self.options["tag"])

        return tag

    def gather_release_notes(self):
        table_of_contents = "<h1>Table of Contents</h1><ul>"
        body = ""
        for project in self.options["repos"]:
            if project["owner"] and project["repo"]:
                release = (
                    self.github.repository(project["owner"], project["repo"])
                    .latest_release()
                    .body
                )
                table_of_contents += (
                    f"""<li><a href="#{project['repo']}">{project['repo']}</a></li>"""
                )
                release_project_header = (
                    f"""<h1 id="{project['repo']}">{project['repo']}</h1>"""
                )
                release_html = self.github.markdown(
                    release,
                    mode="gfm",
                    context="{}/{}".format(project["owner"], project["repo"]),
                )
                body += f"{release_project_header}<hr>{release_html}<hr>"
        table_of_contents += "</ul><br><hr>"
        head = "<head><title>Release Notes</title></head>"
        body = f"<body>{table_of_contents}{body}</body>"
        result = f"<html>{head}{body}</html>"
        with open("github_release_notes.html", "w") as f:
            f.write(result)

    def get_branches(self):
        return scm.get_branches(self.options["source_branch"])

    def compare_commits(self, branch_name, commit):
        return scm.get_commit_diffs(branch_name, commit)

    def compare_commit_count(self, branch_name, commit):
        compare = self.compare_commits(branch_name, commit)
        if not compare or not compare.changes:
            return None
        return len(compare.changes)

    def merge_commit_to_branch(self, branch_name, source, commit, behind_by: None):
        """Attempt to create a pull request from source into branch_name if merge operation encounters a conflict"""
        if branch_name in self.get_existing_prs(
            self.options["source_branch"], self.options["branch_prefix"]
        ):
            self.logger.info(f"Branch {branch_name}: merge PR already exists")
            return

        ret = scm.merge_branch(source, branch_name, self.options)
        if ret is not None:
            self.logger.info(f"Merged {behind_by} commits into branch: {branch_name}")

    def validate_branch(self, branch):
        """Validates that the source branch exists in the repository"""
        scm.validate_branch(branch)

    def get_existing_prs(self, branch, branch_prefix):
        """Returns the existing pull requests from the source branch
        to other branches that are candidates for merging."""
        existing_prs = []

        search_options = {"status": "open", "source_ref_name": f"refs/heads/{branch}"}

        for pr in scm.get_pull_requests(search_options):
            if pr.target_ref_name.startswith(f"refs/heads/{branch_prefix}"):
                existing_prs.append(pr.target_ref_name.replace("refs/heads/", ""))

        return existing_prs

    def create_pull_request(self):
        # Already handled during the merge commit.
        pass

    # def get_version_id_from_tag(self, tag_name):
    #     self.logger.info(
    #         f"get_version_id_from_tag from Azure module called for tag {tag_name}"
    #     )
    #     # return scm.get_version_id_from_tag(repo, tag_name)
