from cumulusci.tasks.scm_task import ScmTask


class AllGithubReleaseNotes(ScmTask):

    task_options = {
        "repos": {
            "description": (
                "The list of owner, repo key pairs for which to generate release notes."
                + " Ex: 'owner': SalesforceFoundation 'repo': 'NPSP'"
            ),
            "required": True,
        },
    }

    def _run_task(self):
        self.gather_release_notes()


class GithubReleaseNotes(ScmTask):

    task_options = {
        "tag": {
            "description": (
                "The tag to generate release notes for." + " Ex: release/1.2"
            ),
            "required": True,
        },
        "last_tag": {
            "description": (
                "Override the last release tag. This is useful"
                + " to generate release notes if you skipped one or more"
                + " releases."
            )
        },
        "link_pr": {
            "description": (
                "If True, insert link to source pull request at" + " end of each line."
            )
        },
        "publish": {"description": "Publish to SCM release if True (default=False)"},
        "include_empty": {
            "description": "If True, include links to PRs that have no release notes (default=False)"
        },
        "version_id": {
            "description": "The package version id used by the InstallLinksParser to add install urls"
        },
        "trial_info": {
            "description": "If True, Includes trialforce template text for this product."
        },
        "sandbox_date": {
            "description": "The date of the sandbox release in ISO format (Will default to None)"
        },
        "production_date": {
            "description": "The date of the production release in ISO format (Will default to None)"
        },
    }

    def _run_task(self):
        self.github_release_notes(self)


class ParentPullRequestNotes(ScmTask):
    task_docs = """
    Aggregate change notes from child pull request(s) to a corresponding parent pull request.

    When given the branch_name option, this task will: (1) check if the base branch
    of the corresponding pull request starts with the feature branch prefix and if so (2) attempt
    to query for a pull request corresponding to this parent feature branch. (3) if a pull request
    isn't found, the task exits and no actions are taken.

    If the build_notes_label is present on the pull request, then all notes from the
    child pull request are aggregated into the parent pull request. if the build_notes_label
    is not detected on the parent pull request then a link to the child pull request
    is placed under the "Unaggregated Pull Requests" header.

    If you have a pull request on branch feature/myFeature that you would like to rebuild notes
    for use the branch_name and force options:
        cci task run github_parent_pr_notes --branch-name feature/myFeature --force True
    """

    task_options = {
        "branch_name": {
            "description": "Name of branch to check for parent status, and if so, reaggregate change notes from child branches.",
            "required": True,
        },
        "build_notes_label": {
            "description": (
                "Name of the label that indicates that change notes on parent pull "
                "requests should be reaggregated when a child branch pull request is created."
            ),
            "required": True,
        },
        "force": {
            "description": "force rebuilding of change notes from child branches in the given branch.",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super(ParentPullRequestNotes, self)._init_options(kwargs)
        self.options["branch_name"] = self.options.get("branch_name")
        self.options["build_notes_label"] = self.options.get("build_notes_label")
        self.options["force"] = self.options.get("force")

    def _run_task(self):
        self.parent_pr_notes()
