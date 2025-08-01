import github3.exceptions

from cumulusci.core.github import (
    get_pull_requests_with_base_branch,
    is_pull_request_merged,
)
from cumulusci.core.utils import import_global
from cumulusci.tasks.release_notes.exceptions import CumulusCIException
from cumulusci.tasks.release_notes.generator import (
    BaseReleaseNotesGenerator,
    render_empty_pr_section,
)
from cumulusci.vcs.github.release_notes.parser import GithubLinesParser, parser_configs
from cumulusci.vcs.github.release_notes.provider import GithubChangeNotesProvider


class ParentPullRequestNotesGenerator(BaseReleaseNotesGenerator):
    """Aggregates notes from child pull requests in to a parent pull request"""

    # Header where unaggregated child pull requests are linked to
    UNAGGREGATED_SECTION_HEADER = "\r\n\r\n# Unaggregated Pull Requests"

    def __init__(self, github, repo, project_config):

        self.repo = repo
        self.github = github
        self.github_info = {
            "github_owner": project_config.repo_owner,
            "github_repo": project_config.repo_name,
            "prefix_beta": project_config.project__git__prefix_beta,
            "prefix_prod": project_config.project__git__prefix_release,
        }
        self.link_pr = True  # create links to pr on parsed change notes
        self.has_issues = True  # need for parsers
        self.do_publish = True  # need for parsers
        self.parser_config = parser_configs(project_config)
        super(ParentPullRequestNotesGenerator, self).__init__()

    def _init_parsers(self):
        """Invoked from Super Class"""
        for cfg in self.parser_config:
            if cfg["class_path"] is not None:
                parser_class = import_global(cfg["class_path"])
                self.parsers.append(parser_class(self, cfg["title"]))

        # Additional parser to collect developer notes above tracked headers
        self.parsers.append(GithubLinesParser(self, title=None))
        self.parsers[-1]._in_section = True

    def aggregate_child_change_notes(self, pull_request):
        """Given a pull request, aggregate all change notes from child pull requests.
        Child pull requests are pull requests that have a base branch
        equal to the the given pull request's head."""
        self.change_notes = get_pull_requests_with_base_branch(
            self.repo, pull_request.head.ref, state="all"
        )
        self.change_notes = [
            note
            for note in self.change_notes
            if is_pull_request_merged(note)
            and note.head.ref != self.repo.default_branch
        ]
        if len(self.change_notes) == 0:
            return

        for change_note in self.change_notes:
            self._parse_change_note(change_note)

        body = []
        for parser in self.parsers:
            if parser.title is None:
                parser.title = "Notes From Child PRs"
            parser_content = parser.render()
            if parser_content:
                body.append(parser_content)

        if self.empty_change_notes:
            body.extend(render_empty_pr_section(self.empty_change_notes))
        new_body = "\r\n".join(body)

        if not pull_request.update(body=new_body):
            raise CumulusCIException(
                "Update of pull request #{} failed.".format(pull_request.number)
            )


class GithubReleaseNotesGenerator(BaseReleaseNotesGenerator):
    def __init__(
        self,
        github,
        github_info,
        parser_config,
        current_tag,
        last_tag=None,
        link_pr=False,
        publish=False,
        has_issues=True,
        include_empty=False,
        version_id=None,
        trial_info=False,
        sandbox_date=None,
        production_date=None,
    ):
        self.github = github
        self.github_info = github_info
        self.parser_config = parser_config
        self.current_tag = current_tag
        self.last_tag = last_tag
        self.link_pr = link_pr
        self.do_publish = publish
        self.has_issues = has_issues
        self.include_empty_pull_requests = include_empty
        self.lines_parser_class = None
        self.issues_parser_class = None
        super(GithubReleaseNotesGenerator, self).__init__()
        self.version_id = version_id
        self.trial_info = trial_info
        self.sandbox_date = sandbox_date
        self.production_date = production_date

    def __call__(self):
        release = self._get_release()
        content = super(GithubReleaseNotesGenerator, self).__call__()
        content = self._update_release_content(release, content)
        if self.do_publish:
            release.edit(body=content)
        return content

    def _init_parsers(self):
        for cfg in self.parser_config:
            if cfg["class_path"] is None:
                continue
            parser_class = import_global(cfg["class_path"])
            self.parsers.append(parser_class(self, cfg["title"]))

    def _init_change_notes(self):
        return GithubChangeNotesProvider(self, self.current_tag, self.last_tag)

    def _get_release(self):
        repo = self.get_repo()
        try:
            return repo.release_from_tag(self.current_tag)
        except github3.exceptions.NotFoundError:
            raise CumulusCIException(
                "Release not found for tag: {}".format(self.current_tag)
            )

    def _update_release_content(self, release, content):
        """Merge existing and new release content."""
        new_body = []
        if release.body:
            current_parser = None
            current_lines = []
            is_start_line = False
            for parser in self.parsers:
                parser.replaced = False

            # update existing sections
            for line in release.body.splitlines():

                if current_parser:
                    if current_parser._is_end_line(current_parser._process_line(line)):
                        parser_content = current_parser.render(
                            "\r\n".join(current_lines)
                        )
                        if parser_content:
                            # replace existing section with new content
                            new_body.append(parser_content + "\r\n")
                        current_parser = None
                        current_lines = []

                for parser in self.parsers:
                    if (
                        parser._render_header().strip()
                        == parser._process_line(line).strip()
                    ):
                        parser.replaced = True
                        current_parser = parser
                        current_lines = []
                        is_start_line = True
                        break
                    else:
                        is_start_line = False

                current_lines.append(line)
                if is_start_line:
                    continue
                if current_parser:
                    continue
                else:
                    # preserve existing sections
                    new_body.append(line.strip())

            # catch section without end line
            if current_parser:
                parser_content = current_parser.render("\r\n".join(current_lines))
                new_body.append(parser_content)

            # add new sections at bottom
            for parser in self.parsers:
                if not parser.replaced:
                    parser_content = parser.render("")
                    if parser_content:
                        new_body.append(parser_content + "\r\n")

        else:  # no release.body
            new_body.append(content)

        # add empty PR section
        if self.include_empty_pull_requests:
            new_body.extend(render_empty_pr_section(self.empty_change_notes))

        content = "\r\n".join(new_body)
        return content

    def get_repo(self):
        return self.github.repository(
            self.github_info["github_owner"], self.github_info["github_repo"]
        )
