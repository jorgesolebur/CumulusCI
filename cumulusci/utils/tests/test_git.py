import pytest

from cumulusci.utils.git import (
    EMPTY_URL_MESSAGE,
    construct_release_branch_name,
    get_parent_branch_candidates,
    get_release_identifier,
    is_release_branch,
    is_release_branch_or_child,
    parse_repo_url,
    split_repo_url,
)
from cumulusci.utils.yaml.cumulusci_yml import ReleaseBranchFormat


def test_is_release_branch():
    assert is_release_branch("feature/230", "feature/")
    assert not is_release_branch("feature/230__test", "feature/")
    assert not is_release_branch("main", "feature/")


def test_is_release_branch_or_child():
    assert is_release_branch_or_child("feature/230", "feature/")
    assert is_release_branch_or_child("feature/230__test", "feature/")
    assert is_release_branch_or_child("feature/230__test__gc", "feature/")
    assert not is_release_branch_or_child("main", "feature/")


def test_get_release_identifier():
    assert get_release_identifier("feature/230", "feature/") == "230"
    assert get_release_identifier("feature/230__test", "feature/") == "230"
    assert get_release_identifier("main", "feature/") is None


def test_construct_release_branch_name():
    assert construct_release_branch_name("feature/", "230") == "feature/230"


class TestGitWithFormatConfig:
    """Tests for format_config parameter (custom release branch formats)."""

    def test_is_release_branch__sequential_with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert is_release_branch("feature/rel-230", "feature/", fmt) is True
        assert is_release_branch("feature/rel-230__test", "feature/", fmt) is False
        assert is_release_branch("feature/230", "feature/", fmt) is False

    def test_is_release_branch_or_child__sequential_with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert is_release_branch_or_child("feature/rel-230", "feature/", fmt) is True
        assert (
            is_release_branch_or_child("feature/rel-230__test", "feature/", fmt) is True
        )

    def test_is_release_branch_or_child__date_format(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        assert is_release_branch_or_child("feature/2025-Q1", "feature/", fmt) is True
        assert (
            is_release_branch_or_child("feature/2025-Q1__test", "feature/", fmt) is True
        )
        assert is_release_branch_or_child("feature/230", "feature/", fmt) is False

    def test_is_release_branch_or_child__fyyyqnsn(self):
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert is_release_branch_or_child("feature/FY26Q3S3", "feature/", fmt) is True
        assert (
            is_release_branch_or_child("feature/FY26Q3S3__test", "feature/", fmt)
            is True
        )

    def test_get_release_identifier__sequential_with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert get_release_identifier("feature/rel-230", "feature/", fmt) == "230"
        assert get_release_identifier("feature/rel-230__test", "feature/", fmt) == "230"

    def test_get_release_identifier__date_format(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        assert get_release_identifier("feature/2025-Q1", "feature/", fmt) == "2025-Q1"
        assert (
            get_release_identifier("feature/2025-Q1__test", "feature/", fmt)
            == "2025-Q1"
        )

    def test_backward_compat__no_format_config(self):
        """Without format_config, behavior matches original (integer-only)."""
        assert is_release_branch("feature/230", "feature/") is True
        assert is_release_branch_or_child("feature/230__test", "feature/") is True
        assert get_release_identifier("feature/230", "feature/") == "230"
        assert get_release_identifier("feature/rel-230", "feature/") is None


class TestGetParentBranchCandidates:
    """Tests for get_parent_branch_candidates — ordered list of parent branches."""

    # ------------------------------------------------------------------
    # No format_config (integer release identifiers)
    # ------------------------------------------------------------------

    def test_single_child_returns_root_only(self):
        """release/001__enhancement1 has one parent: the root release/001."""
        assert get_parent_branch_candidates(
            "release/001__enhancement1", "release/"
        ) == ["release/001"]

    def test_two_level_child_returns_intermediate_then_root(self):
        """release/001__1.1__enhancement3 → [release/001__1.1, release/001]."""
        assert get_parent_branch_candidates(
            "release/001__1.1__enhancement3", "release/"
        ) == ["release/001__1.1", "release/001"]

    def test_three_level_child_returns_all_ancestors_in_order(self):
        """release/001__1.1__1.1.1__enh5 → [release/001__1.1__1.1.1, release/001__1.1, release/001]."""
        assert get_parent_branch_candidates(
            "release/001__1.1__1.1.1__enh5", "release/"
        ) == [
            "release/001__1.1__1.1.1",
            "release/001__1.1",
            "release/001",
        ]

    def test_root_branch_returns_empty(self):
        """release/001 is a root — it has no parent candidates."""
        assert get_parent_branch_candidates("release/001", "release/") == []

    def test_non_release_branch_returns_empty(self):
        """main is not a release branch — returns empty list."""
        assert get_parent_branch_candidates("main", "release/") == []

    # ------------------------------------------------------------------
    # With format_config (FYyyQqSn date format, prefix "FY")
    # ------------------------------------------------------------------

    def test_single_child_with_format_config_returns_root(self):
        """feature/FY26Q4S4__enhancement1 → [feature/FY26Q4S4]."""
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_parent_branch_candidates(
            "feature/FY26Q4S4__enhancement1", "feature/", fmt
        ) == ["feature/FY26Q4S4"]

    def test_two_level_child_with_format_config(self):
        """feature/FY26Q4S4__group__enhancement4 → [feature/FY26Q4S4__group, feature/FY26Q4S4]."""
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_parent_branch_candidates(
            "feature/FY26Q4S4__group__enhancement4", "feature/", fmt
        ) == ["feature/FY26Q4S4__group", "feature/FY26Q4S4"]

    def test_root_with_format_config_returns_empty(self):
        """feature/FY26Q4S4 is the root — returns empty list."""
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_parent_branch_candidates("feature/FY26Q4S4", "feature/", fmt) == []

    def test_non_release_branch_with_format_config_returns_empty(self):
        """main does not match the format — returns empty list."""
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_parent_branch_candidates("main", "feature/", fmt) == []


@pytest.mark.parametrize(
    "repo_uri,owner,repo_name,host",
    [
        (
            "https://git.ent.example.com/org/private_repo/",
            "org",
            "private_repo",
            "git.ent.example.com",
        ),
        ("https://github.com/owner/repo_name/", "owner", "repo_name", "github.com"),
        ("https://github.com/owner/repo_name.git", "owner", "repo_name", "github.com"),
        (
            "https://user@github.com/owner/repo_name.git",
            "owner",
            "repo_name",
            "github.com",
        ),
        (
            "https://git.ent.example.com/org/private_repo.git",
            "org",
            "private_repo",
            "git.ent.example.com",
        ),
        ("git@github.com:owner/repo_name.git", "owner", "repo_name", "github.com"),
        ("git@github.com:/owner/repo_name.git", "owner", "repo_name", "github.com"),
        ("git@github.com:owner/repo_name", "owner", "repo_name", "github.com"),
        (
            "git@api.github.com/owner/repo_name/",
            "owner",
            "repo_name",
            "api.github.com",
        ),
        (
            "git@api.github.com/owner/repo_name.git",
            "owner",
            "repo_name",
            "api.github.com",
        ),
    ],
)
def test_parse_repo_url(repo_uri, owner, repo_name, host):
    assert parse_repo_url(repo_uri) == (owner, repo_name, host)
    assert split_repo_url(repo_uri) == (owner, repo_name)


@pytest.mark.parametrize("URL", [None, ""])
def test_empty_url(URL):
    with pytest.raises(ValueError, match=EMPTY_URL_MESSAGE):
        parse_repo_url(URL)
