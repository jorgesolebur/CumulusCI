import abc
from typing import Any, List, Optional

from cumulusci.core.config.project_config import BaseProjectConfig
from cumulusci.core.dependencies.github import (
    VCS_GITHUB,
    BaseGitHubDependency,
    get_github_repo,
)
from cumulusci.core.dependencies.resolvers import (
    AbstractReleaseTagResolver,
    AbstractTagResolver,
    AbstractUnmanagedHeadResolver,
    AbstractVcsCommitStatusPackageResolver,
    AbstractVcsReleaseBranchResolver,
    DependencyResolutionStrategy,
)
from cumulusci.core.exceptions import DependencyResolutionError
from cumulusci.utils.git import get_feature_branch_name
from cumulusci.vcs.github.adapter import GitHubBranch, GitHubRepository


class GitHubTagResolver(AbstractTagResolver):
    """Resolver that identifies a ref by a specific GitHub tag."""

    name = "GitHub Tag Resolver"
    vcs = VCS_GITHUB

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubReleaseTagResolver(AbstractReleaseTagResolver):
    """Resolver that identifies a ref by finding the latest GitHub release."""

    name = "GitHub Release Resolver"
    vcs = VCS_GITHUB

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubBetaReleaseTagResolver(GitHubReleaseTagResolver):
    """Resolver that identifies a ref by finding the latest GitHub release, including betas."""

    name = "GitHub Release Resolver (Betas)"
    include_beta = True


class GitHubUnmanagedHeadResolver(AbstractUnmanagedHeadResolver):
    """Resolver that identifies a ref by finding the latest commit on the main branch."""

    name = "GitHub Unmanaged Resolver"
    vcs = VCS_GITHUB

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubReleaseBranchCommitStatusResolver(AbstractVcsReleaseBranchResolver):
    """Resolver that identifies a ref by finding a beta 2GP package version
    in a commit status on a `feature/NNN` release branch."""

    name = "GitHub Release Branch Commit Status Resolver"
    commit_status_context = "2gp_context"
    commit_status_default = "Build Feature Test Package"
    branch_offset_start = 0
    branch_offset_end = 1

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubReleaseBranchUnlockedResolver(AbstractVcsReleaseBranchResolver):
    """Resolver that identifies a ref by finding an unlocked package version
    in a commit status on a `feature/NNN` release branch."""

    name = "GitHub Release Branch Unlocked Commit Status Resolver"
    commit_status_context = "unlocked_context"
    commit_status_default = "Build Unlocked Test Package"
    branch_offset_start = 0
    branch_offset_end = 1

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubPreviousReleaseBranchCommitStatusResolver(AbstractVcsReleaseBranchResolver):
    """Resolver that identifies a ref by finding a beta 2GP package version
    in a commit status on a `feature/NNN` release branch that is earlier
    than the matching local release branch."""

    name = "GitHub Previous Release Branch Commit Status Resolver"
    commit_status_context = "2gp_context"
    commit_status_default = "Build Feature Test Package"
    branch_offset_start = 1
    branch_offset_end = 3

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class GitHubPreviousReleaseBranchUnlockedResolver(AbstractVcsReleaseBranchResolver):
    """Resolver that identifies a ref by finding an unlocked package version
    in a commit status on a `feature/NNN` release branch that is earlier
    than the matching local release branch."""

    name = "GitHub Previous Release Branch Unlocked Commit Status Resolver"
    commit_status_context = "unlocked_context"
    commit_status_default = "Build Unlocked Test Package"
    branch_offset_start = 1
    branch_offset_end = 3

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)


class AbstractGitHubExactMatchCommitStatusResolver(
    AbstractVcsCommitStatusPackageResolver, abc.ABC
):
    """Abstract base class for resolvers that identify a ref by finding a package version
    in a commit status on a branch whose name matches the local branch."""

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)

    def get_branches(
        self,
        dep: BaseGitHubDependency,
        context: BaseProjectConfig,
    ) -> List[GitHubBranch]:
        repo = self.get_repo(context, dep.url)
        if not repo:
            raise DependencyResolutionError(
                f"Unable to access GitHub repository for {dep.url}"
            )

        # Use the local context's prefix so that release/ branches are matched
        # with the release prefix, not always the feature prefix from the remote.
        try:
            branch_prefix, _ = context.get_release_branch_prefix_and_format_config()
            branch = get_feature_branch_name(context.repo_branch, branch_prefix)
            release_branch = repo.branch(f"{branch_prefix}{branch}")
        except Exception:
            context.logger.info(
                f"Could not find exact-match branch or prefix for {repo.clone_url}. Unable to resolve package."
            )
            return []

        return [release_branch]


class GitHubExactMatch2GPResolver(AbstractGitHubExactMatchCommitStatusResolver):
    """Resolver that identifies a ref by finding a 2GP package version
    in a commit status on a branch whose name matches the local branch."""

    name = "GitHub Exact-Match Commit Status Resolver"
    commit_status_context = "2gp_context"
    commit_status_default = "Build Feature Test Package"


class GitHubExactMatchUnlockedCommitStatusResolver(
    AbstractGitHubExactMatchCommitStatusResolver
):
    """Resolver that identifies a ref by finding an unlocked package version
    in a commit status on a branch whose name matches the local branch."""

    name = "GitHub Exact-Match Unlocked Commit Status Resolver"
    commit_status_context = "unlocked_context"
    commit_status_default = "Build Unlocked Test Package"


class AbstractGitHubDefaultBranchCommitStatusResolver(
    AbstractVcsCommitStatusPackageResolver, abc.ABC
):
    """Abstract base class for resolvers that identify a ref by finding a beta package version
    in a commit status on the repo's default branch."""

    def get_repo(
        self, context: BaseProjectConfig, url: Optional[str]
    ) -> GitHubRepository:
        return get_github_repo(context, url)

    def get_branches(
        self,
        dep: BaseGitHubDependency,
        context: BaseProjectConfig,
    ) -> List[GitHubBranch]:
        repo = self.get_repo(context, dep.url)

        return [repo.branch(repo.default_branch)]


class GitHubDefaultBranch2GPResolver(AbstractGitHubDefaultBranchCommitStatusResolver):
    name = "GitHub Default Branch Commit Status Resolver"
    commit_status_context = "2gp_context"
    commit_status_default = "Build Feature Test Package"


class GitHubDefaultBranchUnlockedCommitStatusResolver(
    AbstractGitHubDefaultBranchCommitStatusResolver
):
    name = "GitHub Default Branch Unlocked Commit Status Resolver"
    commit_status_context = "unlocked_context"
    commit_status_default = "Build Unlocked Test Package"


GITHUB_RESOLVER_CLASSES: dict[str, type[Any]] = {
    DependencyResolutionStrategy.STATIC_TAG_REFERENCE: GitHubTagResolver,
    DependencyResolutionStrategy.COMMIT_STATUS_EXACT_BRANCH: GitHubExactMatch2GPResolver,
    DependencyResolutionStrategy.COMMIT_STATUS_RELEASE_BRANCH: GitHubReleaseBranchCommitStatusResolver,
    DependencyResolutionStrategy.COMMIT_STATUS_PREVIOUS_RELEASE_BRANCH: GitHubPreviousReleaseBranchCommitStatusResolver,
    DependencyResolutionStrategy.COMMIT_STATUS_DEFAULT_BRANCH: GitHubDefaultBranch2GPResolver,
    DependencyResolutionStrategy.BETA_RELEASE_TAG: GitHubBetaReleaseTagResolver,
    DependencyResolutionStrategy.RELEASE_TAG: GitHubReleaseTagResolver,
    DependencyResolutionStrategy.UNMANAGED_HEAD: GitHubUnmanagedHeadResolver,
    DependencyResolutionStrategy.UNLOCKED_EXACT_BRANCH: GitHubExactMatchUnlockedCommitStatusResolver,
    DependencyResolutionStrategy.UNLOCKED_RELEASE_BRANCH: GitHubReleaseBranchUnlockedResolver,
    DependencyResolutionStrategy.UNLOCKED_PREVIOUS_RELEASE_BRANCH: GitHubPreviousReleaseBranchUnlockedResolver,
    DependencyResolutionStrategy.UNLOCKED_DEFAULT_BRANCH: GitHubDefaultBranchUnlockedCommitStatusResolver,
}
