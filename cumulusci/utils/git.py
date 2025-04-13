import pathlib
import re
from typing import Any, Optional, Tuple

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


def current_branch(repo_root: str) -> Optional[str]:
    if repo_root:
        head_path = git_path(repo_root, "HEAD")
        if head_path.exists():
            branch_ref = head_path.read_text().strip()
            if branch_ref.startswith("ref: "):
                return "/".join(branch_ref[5:].split("/")[2:])


def is_release_branch(branch_name: str, prefix: str) -> bool:
    """A release branch begins with the given prefix"""
    if not branch_name.startswith(prefix):
        return False
    parts = branch_name[len(prefix) :].split("__")
    return len(parts) == 1 and parts[0].isdigit()


def is_release_branch_or_child(branch_name: str, prefix: str) -> bool:
    if not branch_name.startswith(prefix):
        return False
    parts = branch_name[len(prefix) :].split("__")
    return len(parts) >= 1 and parts[0].isdigit()


def get_feature_branch_name(branch_name: str, prefix: str) -> Optional[str]:
    if branch_name.startswith(prefix):
        return branch_name[len(prefix) :]


def get_release_identifier(branch_name: str, prefix: str) -> Optional[str]:
    if is_release_branch_or_child(branch_name, prefix):
        return get_feature_branch_name(branch_name, prefix).split("__")[0]


def construct_release_branch_name(prefix: str, release_identifier: str) -> str:
    return f"{prefix}{release_identifier}"


def split_repo_url(url: str) -> Tuple[str, str]:
    owner, name, _, _ = parse_repo_url(url)
    return (owner, name)


def parse_repo_url(url: str) -> Tuple[str, str, str, str]:
    """Parses a given Github URI into Owner, Repo Name, Host and Project (for Azure urls)

    Parameters
    ----------
    url: str
        A github URI. Examples: ["https://github.com/owner/repo/","https://github.com/owner/repo.git","git@github.com:owner/repo.git", "https://api.github.com/repos/owner/repo_name/"]
        A Azure URI. Examples: ["https://user@dev.azure.com/[org|user]/project/_git/repo", "git@ssh.dev.azure.com:v3/[user|org]/project/repo"]
    Returns
    -------
    Tuple: (str, str, str, str)
        Returns (owner, name, host, project)
    """
    if not url:
        raise ValueError(EMPTY_URL_MESSAGE)

    from urllib.parse import urlparse

    formatted_url = f"ssh://{url}" if url.startswith("git") else url
    parse_result = urlparse(formatted_url)

    host = parse_result.hostname

    url_parts = re.split("/|@|:", parse_result.path.rstrip("/").lstrip("/"))
    url_parts = list(filter(None, url_parts))

    name = url_parts[-1]
    if name.endswith(".git"):
        name = name[:-4]

    owner = (
        parse_result._hostinfo[-1]
        if url.startswith("git") and parse_result._hostinfo[-1] is not None
        else url_parts[-2]
    )
    project = None

    if "azure" in host:
        if owner == "v3" or parse_result.scheme == "https":
            owner = url_parts[0]  # Set organization as the owner.
        project = url_parts[1]

    return (owner, name, host, project)
