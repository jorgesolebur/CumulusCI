from datetime import datetime

import cumulusci.core.github as scm
from cumulusci.core.tasks import BaseScmTask
from cumulusci.core.utils import process_bool_arg
from cumulusci.tasks.release_notes.generator import (
    GithubReleaseNotesGenerator,
    ParentPullRequestNotesGenerator,
)


class BaseGithubTask(BaseScmTask):
    UNAGGREGATED_PR_HEADER = "\r\n\r\n# Unaggregated Pull Requests"

    def _init_task(self):
        super()._init_task()
        self.github_config = self.project_config.keychain.get_service("github")
        self.github = scm.get_github_api_for_repo(
            self.project_config.keychain, self.project_config.repo_url
        )

    def get_repo(self):
        return self.github.repository(
            self.project_config.repo_owner, self.project_config.repo_name
        )

    def get_tag_by_name(self, repo, src_tag_name):
        return scm.get_tag_by_name(repo, src_tag_name)

    def create_tag(self):
        src_tag_name = self.options["src_tag"]
        repo = self.get_repo()
        src_tag = self.get_tag_by_name(repo, src_tag_name)
        tag = repo.create_tag(
            tag=self.options["tag"],
            message=f"Cloned from {src_tag_name}",
            sha=src_tag.sha,
            obj_type="commit",
            tagger={
                "name": self.github_config.username,
                "email": self.github_config.email,
                "date": f"{datetime.utcnow().isoformat()}Z",
            },
        )
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

    def release_notes(self):
        github_info = {
            "github_owner": self.project_config.repo_owner,
            "github_repo": self.project_config.repo_name,
            "github_username": self.github_config.username,
            "github_password": self.github_config.password,
            "default_branch": self.project_config.project__git__default_branch,
            "prefix_beta": self.project_config.project__git__prefix_beta,
            "prefix_prod": self.project_config.project__git__prefix_release,
        }

        generator = GithubReleaseNotesGenerator(
            self.github,
            github_info,
            self.project_config.project__git__release_notes__parsers.values(),
            self.options["tag"],
            self.options.get("last_tag"),
            process_bool_arg(self.options.get("link_pr", False)),
            process_bool_arg(self.options.get("publish", False)),
            self.get_repo().has_issues,
            process_bool_arg(self.options.get("include_empty", False)),
            version_id=self.options.get("version_id"),
            trial_info=self.options.get("trial_info", False),
            sandbox_date=self.options.get("sandbox_date", None),
            production_date=self.options.get("production_date", None),
        )

        release_notes = generator()
        self.logger.info("\n" + release_notes)

    def _setup_pr_notes_self(self):
        self.repo = self.get_repo()
        self.commit = self.repo.commit(self.project_config.repo_commit)
        self.branch_name = self.options.get("branch_name")
        self.force_rebuild_change_notes = process_bool_arg(
            self.options["force"] or False
        )
        self.generator = ParentPullRequestNotesGenerator(
            self.github, self.repo, self.project_config
        )

    def parent_pr_notes(self):
        self._setup_pr_notes_self()

        if self.force_rebuild_change_notes:
            pull_request = self._get_parent_pull_request()
            if pull_request:
                self.generator.aggregate_child_change_notes(pull_request)

        elif self._has_parent_branch() and self._commit_is_merge():
            parent_pull_request = self._get_parent_pull_request()
            if parent_pull_request:
                if scm.is_label_on_pull_request(
                    self.repo,
                    parent_pull_request,
                    self.options.get("build_notes_label"),
                ):
                    self.generator.aggregate_child_change_notes(parent_pull_request)
                else:
                    child_branch_name = self._get_child_branch_name_from_merge_commit()
                    if child_branch_name:
                        self._update_unaggregated_pr_header(
                            parent_pull_request, child_branch_name
                        )

    def _has_parent_branch(self):
        feature_prefix = self.project_config.project__git__prefix_feature
        return (
            self.branch_name.startswith(feature_prefix) and "__" not in self.branch_name
        )

    def _commit_is_merge(self):
        return len(self.commit.parents) > 1

    def _get_parent_pull_request(self):
        """Attempts to retrieve a pull request for the given branch."""
        requests = scm.get_pull_requests_with_base_branch(
            self.repo, self.repo.default_branch, self.branch_name
        )
        if len(requests) > 0:
            return requests[0]
        else:
            self.logger.info(f"Pull request not found for branch {self.branch_name}.")

    def _get_child_branch_name_from_merge_commit(self):
        pull_requests = scm.get_pull_requests_by_commit(
            self.github, self.repo, self.commit.sha
        )
        merged_prs = list(filter(scm.is_pull_request_merged, pull_requests))

        child_branch_name = None
        if len(merged_prs) == 1:
            return merged_prs[0].head.ref

        else:
            self.logger.error(
                f"Received multiple pull requests, expected one, for commit sha: {self.commit.sha}"
            )

        return child_branch_name

    def _update_unaggregated_pr_header(
        self, pull_request_to_update, branch_name_to_add
    ):
        """Updates the 'Unaggregated Pull Requests' section header with a link
        to the new child branch pull request"""

        self._add_header(pull_request_to_update)

        pull_requests = scm.get_pull_requests_with_base_branch(
            self.repo,
            branch_name_to_add.split("__")[0],
            branch_name_to_add,
            state="all",
        )

        if len(pull_requests) == 0:
            self.logger.info(f"No pull request for branch {branch_name_to_add} found.")
        elif len(pull_requests) > 1:
            self.logger.error(
                f"Expected one pull request, found {len(pull_requests)} for branch {branch_name_to_add}"
            )
        else:
            self._add_link_to_pr(pull_request_to_update, pull_requests[0])

    def _add_header(self, pull_request):
        """Appends the header to the pull_request.body if not already present"""
        pull_request.body = "" if pull_request.body is None else pull_request.body
        if self.UNAGGREGATED_PR_HEADER not in pull_request.body:
            pull_request.body += self.UNAGGREGATED_PR_HEADER

    def _add_link_to_pr(self, to_update, to_link):
        """Updates pull request to_update with a link to pull
        request to_link if one does not already exist."""
        body = to_update.body
        pull_request_link = scm.markdown_link_to_pr(to_link)
        if pull_request_link not in body:
            body += "\r\n* " + pull_request_link
            to_update.update(body=body)

    # def get_version_id_from_tag(self, tag_name):
    #     self.logger.info(f"get_version_id_from_tag from Github module called for tag {tag_name}")
    #     return scm.get_version_id_from_tag(self.get_repo(), tag_name)
