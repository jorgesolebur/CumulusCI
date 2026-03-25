"""Release branch format handling for custom branch naming schemes.

Supports sequential (integer, optional prefix), date-based formats
(yy, yyyy-mm, yyyy-mm-dd, yyyy-qn, yyyy-SPRINTn), and FYyyQqSn
(fy, q, s). Date formats accept 2- or 4-digit years
(e.g. 26 or 2026).

All regex tokens are lowercase: yy (2-digit year), yyyy (2 or 4-digit year),
mm (month), dd (day), q (quarter 1-4), n (sprint number).
Uppercase in the pattern (Sprint, FY, Q, S) are literal strings in branch
names and are not replaced.
"""

import re
from functools import lru_cache
from typing import TYPE_CHECKING, List, Optional, Tuple

from cumulusci.utils.yaml.cumulusci_yml import ReleaseBranchFormat

if TYPE_CHECKING:  # pragma: no cover - only runs during type checking
    from cumulusci.core.config.project_config import BaseProjectConfig

# Lowercase tokens = replaced with regex; uppercase = literal (not replaced)
# Longest tokens first to avoid partial matches
# Named groups allow access via m.group('mm'), m.group('dd'), etc.
_PATTERN_TOKENS = [
    ("yyyy", r"(?P<yyyy>\d{2}|\d{4})", (0, 99)),
    ("yy", r"(?P<yy>\d{2})", (0, 9999)),
    ("mm", r"(?P<mm>\d{2})", (1, 12)),
    ("dd", r"(?P<dd>\d{2})", (1, 31)),
    ("q", r"(?P<q>[1-4])", (1, 4)),
    ("n", r"(?P<n>\d+$)", (0, 9999)),
]
_NAMED_GROUPS = frozenset(token for token, _, _ in _PATTERN_TOKENS)
_GROUP_ORDER_REVERSE = [token for token, _, _ in reversed(_PATTERN_TOKENS)]


@lru_cache(maxsize=32)
def pattern_to_regex(pattern: str) -> Tuple[re.Pattern[str], list[str]]:
    """Convert a pattern string (e.g. mm-dd, yyyy-mm) to a compiled regex.

    Lowercase tokens (yy, yyyy, mm, dd, q, n) are replaced with regex.
    Uppercase in the pattern (Sprint, FY, Q, S) are literal strings.
    """
    if not pattern:
        raise ValueError("Pattern cannot be empty")
    result = []
    order = []
    i = 0
    while i < len(pattern):
        matched = False
        for token, regex, _ in _PATTERN_TOKENS:
            chunk = pattern[i : i + len(token)]
            next_pos = i + len(token)
            # Lowercase tokens = placeholders; uppercase in pattern = literal (not replaced)
            # Only match when chunk equals token (lowercase); "n" only at pattern end (not in "Sprint")
            if token == "n":
                matched_token = chunk == "n" and next_pos == len(pattern)
            else:
                matched_token = chunk == token
            if matched_token:
                result.append(regex)
                order.append(token)
                i += len(token)
                matched = True
                break
        if not matched:
            result.append(re.escape(pattern[i]))
            i += 1
    full = r"^" + "".join(result) + r"$"
    return re.compile(full), order


def _reconstruct_identifier_from_groups(pattern: str, group_values: dict) -> str:
    """Reconstruct identifier from pattern and new group values (e.g. yy-mm-n)."""
    parts = []
    i = 0
    while i < len(pattern):
        matched = False
        for token, _, _ in _PATTERN_TOKENS:
            chunk = pattern[i : i + len(token)]
            next_pos = i + len(token)
            if token == "n":
                matched_token = chunk == "n" and next_pos == len(pattern)
            else:
                matched_token = chunk == token
            if matched_token:
                val = str(group_values[token])
                parts.append(val)
                i += len(token)
                matched = True
                break
        if not matched:
            parts.append(pattern[i])
            i += 1
    return "".join(parts)


def parse_format_config(
    config: "Optional[BaseProjectConfig]",
) -> Optional[ReleaseBranchFormat]:
    """Load release branch format from project config.

    Returns None when no release_branch_format is configured (backward compatible).
    """
    if config is None:
        return None

    type_val = config.project__git__release_branch_format__type
    if type_val is None:
        return None

    prefix = config.project__git__release_branch_format__prefix or ""
    pattern = config.project__git__release_branch_format__pattern
    max_sprints = config.project__git__release_branch_format__max_sprints_per_quarter

    return ReleaseBranchFormat(
        type=type_val,
        prefix=prefix,
        pattern=pattern,
        max_sprints_per_quarter=max_sprints,
    )


def is_valid_release_identifier(
    identifier: str, format_config: "Optional[ReleaseBranchFormat]" = None
) -> bool:
    """Validate that the identifier matches the configured format."""
    if format_config is None:
        # Default: integer only
        return identifier.isdigit()

    prefix = format_config.prefix or ""

    if not identifier.startswith(prefix):
        return False

    suffix = identifier[len(prefix) :] if prefix else identifier

    match format_config.type:
        case "sequential":
            return suffix.isdigit()
        case "date":
            return _validate_date_identifier(suffix, format_config)
        case _:
            return False


def _validate_date_identifier(
    identifier: str, format_config: ReleaseBranchFormat
) -> bool:
    """Validate date-format identifier using pattern_to_regex."""
    pattern = format_config.pattern
    if not pattern:
        return False

    try:
        regex, _ = pattern_to_regex(pattern)
    except ValueError:  # pragma: no cover - pattern empty check prevents this
        return False

    m = regex.match(identifier)
    if not m:
        return False
    groups = {k: v for k, v in m.groupdict().items() if k in _NAMED_GROUPS and v}
    try:
        valid_date = True
        if "mm" in groups:
            valid_date = valid_date and 1 <= int(groups["mm"]) <= 12
        if "dd" in groups:
            valid_date = valid_date and 1 <= int(groups["dd"]) <= 31
        if "q" in groups:
            valid_date = valid_date and 1 <= int(groups["q"]) <= 4
        if "n" in groups:
            valid_date = valid_date and int(groups["n"]) >= 0
    except (ValueError, KeyError):  # pragma: no cover - regex ensures valid digits
        return False
    return valid_date


def get_release_identifier(
    branch_name: str,
    prefix: str,
    format_config: Optional[ReleaseBranchFormat] = None,
) -> Optional[str]:
    """Extract release identifier from branch name (e.g. feature/230__x -> 230)."""
    if not branch_name.startswith(prefix):
        return None

    suffix = branch_name[len(prefix) :]

    parts = suffix.split("__")
    identifier = parts[0]
    if format_config is None:
        if identifier.isdigit():
            return identifier
        return None
    if is_valid_release_identifier(identifier, format_config):
        identifier = (
            identifier[len(format_config.prefix) :]
            if format_config.prefix
            else identifier
        )
        return identifier
    return None


def get_previous_identifier(
    identifier: str,
    n: int,
    format_config: Optional[ReleaseBranchFormat] = None,
) -> str:
    """Return the n-th previous identifier. n=0 returns identifier unchanged."""
    if n <= 0:
        return identifier

    if format_config is None:
        # Default: sequential integer
        try:
            val = int(identifier)
            return str(val - n)
        except ValueError:
            raise ValueError(
                f"Cannot compute previous for non-integer identifier: {identifier}"
            )

    if format_config.type == "sequential":
        prefix = format_config.prefix
        if prefix:
            if not identifier.startswith(prefix):
                raise ValueError(
                    f"Identifier {identifier} does not match prefix {prefix}"
                )
            suffix = identifier[len(prefix) :]
            val = int(suffix)
            return f"{prefix}{val - n}"
        return str(int(identifier) - n)

    if format_config.type == "date" and format_config.pattern:
        return _previous_date_identifier(identifier, n, format_config)

    raise ValueError(f"Unknown format type: {format_config.type}")


def _release_identifier_sort_key(
    identifier: str, format_config: Optional[ReleaseBranchFormat] = None
) -> Tuple[int, ...]:
    """Build a sortable tuple for release identifiers.

    Raises:
        ValueError: if identifier cannot be ordered for the given format.
    """
    if format_config is None:
        if not identifier.isdigit():
            raise ValueError(
                f"Cannot order non-numeric identifier without format: {identifier}"
            )
        return (int(identifier),)

    raw = identifier
    prefix = format_config.prefix or ""
    if prefix and raw.startswith(prefix):
        raw = raw[len(prefix) :]

    if format_config.type == "sequential":
        if not raw.isdigit():
            raise ValueError(
                f"Cannot order non-numeric sequential identifier: {identifier}"
            )
        return (int(raw),)

    if format_config.type == "date" and format_config.pattern:
        regex, order = pattern_to_regex(format_config.pattern)
        if not order:
            raise ValueError(f"Pattern {format_config.pattern} has no sortable tokens.")
        m = regex.match(raw)
        if not m:
            raise ValueError(
                f"Identifier {identifier} does not match pattern {format_config.pattern}"
            )
        groups = m.groupdict()
        key = []
        for token in order:
            value = groups.get(token)
            if value is None:
                raise ValueError(
                    f"Missing token {token} in identifier {identifier} for sorting."
                )
            numeric = int(value)
            # Treat 2-digit years as 2000-based for ordering consistency.
            if token in {"yy", "yyyy"} and len(value) == 2:
                numeric += 2000
            key.append(numeric)
        return tuple(key)

    raise ValueError(f"Unknown format type: {format_config.type}")


def sort_release_identifiers(
    identifiers: List[str], format_config: Optional[ReleaseBranchFormat] = None
) -> List[str]:
    """Sort release identifiers in ascending order for configured format."""
    return sorted(
        identifiers, key=lambda item: _release_identifier_sort_key(item, format_config)
    )


def _previous_decrement_with_carry(
    groups: dict,
    pattern: str,
    max_sprints_per_quarter: int = 0,
) -> str:
    """Decrement identifier by looping in reverse order of _NAMED_GROUPS with carry.

    For yy-mm-n (e.g. 26-03-5): decrement n; if n < 1, wrap to max and mm -= 1;
    if mm == 0, wrap to 12 and yy -= 1.
    """
    _, pattern_order = pattern_to_regex(pattern)
    # Reverse order: process rightmost group first (n, mm, yy for yy-mm-n)
    reverse_order = [g for g in _GROUP_ORDER_REVERSE if g in pattern_order]

    # Bounds per group: (min, max)
    bounds = {g: b for g, _, b in _PATTERN_TOKENS if g in pattern_order}
    if max_sprints_per_quarter > 0:
        bounds["n"] = (1, max_sprints_per_quarter)

    values = {}
    for group_name, group_value in groups.items():
        values[group_name] = int(group_value)

    carry = 1
    for group_name in reverse_order:
        if group_name not in pattern_order:
            continue

        if carry == 0:
            break

        min_val, max_val = bounds.get(group_name, (0, 999))

        values[group_name] -= carry
        if values[group_name] < min_val:
            carry = 1
            values[group_name] = max_val
        else:
            carry = 0

    # Format back to strings for reconstruction
    group_values = {}
    for k, v in values.items():
        if k == "yyyy":
            group_values[k] = f"{v:04d}"
        elif k == "mm" or k == "dd" or k == "yy":
            group_values[k] = f"{v:02d}"
        else:
            group_values[k] = str(v)

    return _reconstruct_identifier_from_groups(pattern, group_values)


def _previous_date_identifier(
    identifier: str, n: int, format_config: ReleaseBranchFormat
) -> str:
    """Compute previous identifier for date formats."""
    pattern = format_config.pattern or ""
    regex, _ = pattern_to_regex(pattern)
    m = regex.match(identifier)
    if not m:
        raise ValueError(f"Invalid {pattern} identifier: {identifier}")

    return _previous_decrement_with_carry(
        m.groupdict(),
        pattern,
        format_config.max_sprints_per_quarter if "q" in pattern else 0,
    )
