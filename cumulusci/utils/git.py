import pathlib
import re
from typing import Any, Optional, Tuple
from urllib.parse import ParseResult, urlparse

from cumulusci.utils.release_branch import ReleaseBranchFormat
from cumulusci.utils.release_branch import (
    get_release_identifier as release_branch_get_identifier,
)
from cumulusci.utils.release_branch import is_valid_release_identifier

EMPTY_URL_MESSAGE = """
The provided URL is empty or no URL under git remote "origin".
"""


def git_path(repo_root: str, tail: Any = None) -> Optional[pathlib.Path]:
    """Returns a Path to the .git directory in repo_root
    with tail appended (if present) or None if repo_root is not set.
    """
    path = None
    if repo_root:
        path = pathlib.Path(repo_root) / ".git"
        if tail is not None:
            path = path / str(tail)
    return path


def resolve_worktree_git_dirs(
    repo_root: str,
) -> Tuple[Optional[pathlib.Path], Optional[pathlib.Path]]:
    """Return (worktree_git_dir, common_git_dir) for the given repo root.

    For a normal (non-worktree) repo both values are the same ``.git``
    directory.  For a git worktree checkout ``.git`` is a file whose
    content points to the worktree-specific gitdir; the common gitdir is
    found via that directory's ``commondir`` file.

    Returns ``(None, None)`` when *repo_root* is not set or ``.git`` is
    absent.

    worktree_git_dir  – owns HEAD, index, COMMIT_EDITMSG, etc.
    common_git_dir    – owns config, packed-refs, objects, refs/heads/, etc.
    """
    if not repo_root:
        return None, None

    git_entry = git_path(repo_root)
    if git_entry is None:
        return None, None

    if git_entry.is_dir():
        return git_entry, git_entry

    if git_entry.is_file():
        content = git_entry.read_text().strip()
        if content.startswith("gitdir: "):
            wt_dir = pathlib.Path(content[len("gitdir: ") :])
            if not wt_dir.is_absolute():
                wt_dir = (git_entry.parent / wt_dir).resolve()

            commondir_file = wt_dir / "commondir"
            if commondir_file.exists():
                commondir = commondir_file.read_text().strip()
                common = pathlib.Path(commondir)
                if not common.is_absolute():
                    common = (wt_dir / common).resolve()
                return wt_dir, common

            return wt_dir, wt_dir

    return None, None


def current_branch(repo_root: str) -> Optional[str]:
    if not repo_root:
        return None

    wt_dir, _ = resolve_worktree_git_dirs(repo_root)
    if wt_dir:
        head_path = wt_dir / "HEAD"
        if head_path.exists():
            branch_ref = head_path.read_text().strip()
            if branch_ref.startswith("ref: "):
                return "/".join(branch_ref[5:].split("/")[2:])


def is_release_branch(
    branch_name: str, prefix: str, format_config: Optional[ReleaseBranchFormat] = None
) -> bool:
    """A release branch begins with the given prefix and matches the format."""
    if not branch_name.startswith(prefix):
        return False
    parts = branch_name[len(prefix) :].split("__")
    if not parts:
        return False
    identifier = parts[0]
    if format_config is None:
        return len(parts) == 1 and identifier.isdigit()
    return len(parts) == 1 and is_valid_release_identifier(identifier, format_config)


def is_release_branch_or_child(
    branch_name: str, prefix: str, format_config: Optional[ReleaseBranchFormat] = None
) -> bool:
    """True if branch is a release branch or a child (e.g. feature/230__test)."""
    if not branch_name.startswith(prefix):
        return False
    parts = branch_name[len(prefix) :].split("__")
    if not parts:
        return False
    identifier = parts[0]
    if format_config is None:
        return len(parts) >= 1 and identifier.isdigit()
    return len(parts) >= 1 and is_valid_release_identifier(identifier, format_config)


def get_feature_branch_name(branch_name: str, prefix: str) -> Optional[str]:
    if branch_name.startswith(prefix):
        return branch_name[len(prefix) :]


def get_release_identifier(
    branch_name: str,
    prefix: str,
    format_config: Optional[ReleaseBranchFormat] = None,
) -> Optional[str]:
    """Extract release identifier from branch name."""
    if format_config is not None:
        return release_branch_get_identifier(branch_name, prefix, format_config)
    if is_release_branch_or_child(branch_name, prefix, None):
        return get_feature_branch_name(branch_name, prefix).split("__")[0]


def get_parent_branch_candidates(
    branch_name: str,
    prefix: str,
    format_config: Optional[ReleaseBranchFormat] = None,
) -> list[str]:
    """Return an ordered list of parent branch candidates for a child branch.

    Candidates are ordered from most-specific (immediate parent) to least-specific
    (root release branch). Returns an empty list when ``branch_name`` is not a
    release branch or child of one.

    Examples (prefix ``release/``, no format_config)::

        release/001__1.1__enhancement3  →  [release/001__1.1, release/001]
        release/001__enhancement1       →  [release/001]
        release/001                     →  []  (already the root, no parents)

    Examples (prefix ``feature/``, format_config with prefix ``FY``)::

        feature/FY26Q4S4__group__enhancement4  →  [feature/FY26Q4S4__group, feature/FY26Q4S4]
        feature/FY26Q4S4__enhancement1         →  [feature/FY26Q4S4]
    """
    if not is_release_branch_or_child(branch_name, prefix, format_config):
        return []

    suffix = branch_name[len(prefix) :]
    parts = suffix.split("__")

    # A root release branch (single part) has no parents.
    if len(parts) <= 1:
        return []

    candidates: list[str] = []

    # Intermediate parents: drop the last k segments one at a time.
    # For ['001', '1.1', 'enh'], k=1 → 001__1.1; stops before the root.
    for k in range(1, len(parts) - 1):
        candidates.append(prefix + "__".join(parts[:-k]))

    # Root release branch via format_config-aware construction so that branch
    # prefixes (e.g. "FY" in FY26Q4S4) are re-applied correctly.
    release_id = get_release_identifier(branch_name, prefix, format_config)
    candidates.append(construct_release_branch_name(prefix, release_id, format_config))

    return candidates


def construct_release_branch_name(
    prefix: str,
    release_identifier: str,
    format_config: Optional[ReleaseBranchFormat] = None,
) -> str:
    if format_config is not None:
        return f"{prefix}{format_config.prefix or ''}{release_identifier}"
    return f"{prefix}{release_identifier}"


def split_repo_url(url: str) -> Tuple[str, str]:
    owner, name, _ = parse_repo_url(url)
    return (owner, name)


def parse_repo_url(url: str) -> Tuple[str, str, str]:
    """Parses a given Github URI into Owner, Repo Name, and Host

    Parameters
    ----------
    url: str
        A github URI. Examples: ["https://github.com/owner/repo/","https://github.com/owner/repo.git","git@github.com:owner/repo.git", "https://api.github.com/repos/owner/repo_name/"]

    Returns
    -------
    Tuple: (str, str, str)
        Returns (owner, name, host)
    """
    if not url:
        raise ValueError(EMPTY_URL_MESSAGE)

    url_parts = re.split("/|@|:", url.rstrip("/"))
    url_parts = list(filter(None, url_parts))

    name = url_parts[-1]
    if name.endswith(".git"):
        name = name[:-4]

    owner = url_parts[-2]

    host = url_parts[-3]
    # Regular Expression to match domain of host com,org,in,app etc
    domain_search_exp = re.compile(r"\.[a-zA-Z]+$")
    # Need to consider "https://api.github.com/repos/owner/repo/" pattern
    if (
        "http" in url_parts[0]
        and len(url_parts) > 4
        and domain_search_exp.search(host) is None
    ):
        host = url_parts[-4]
    return (owner, name, host)


def generic_parse_repo_url(
    url: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parses a given URI into Owner, Repo Name, Host and Project

    Parameters
    ----------
    url: str
        A Azure URI. Examples: ["https://user@dev.azure.com/[org|user]/project/_git/repo", "git@ssh.dev.azure.com:v3/[user|org]/project/repo"]
    Returns
    -------
    Tuple: (Optional[str], Optional[str], Optional[str])
        Returns (owner, name with project, host)
    """
    if not url:
        raise ValueError(EMPTY_URL_MESSAGE)

    if url.find("github") >= 0:
        return parse_repo_url(url)

    formatted_url = f"ssh://{url}" if url.startswith("git") else url
    parse_result: ParseResult = urlparse(formatted_url)

    host: str = parse_result.hostname or ""
    host = host.replace("ssh.", "") if url.startswith("git") else host

    url_parts = re.split(
        "/|@|:", parse_result.path.replace("/_git/", "/").rstrip("/").lstrip("/")
    )
    url_parts = list(filter(None, url_parts))

    name: Optional[str] = url_parts[-1]
    if name.endswith(".git"):
        name = name[:-4]

    owner: Optional[str] = url_parts[0]
    project: Optional[str] = f"{url_parts[1]}/" if len(url_parts) > 2 else ""

    return (owner, f"{project}{name}", host)
