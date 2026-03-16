"""Tests for cumulusci.utils.release_branch module."""

from unittest.mock import MagicMock

import pytest

from cumulusci.core.config import BaseProjectConfig, UniversalConfig
from cumulusci.utils.release_branch import (
    _reconstruct_identifier_from_groups,
    construct_release_branch_name,
    get_previous_identifier,
    get_release_identifier,
    is_valid_release_identifier,
    parse_format_config,
    pattern_to_regex,
)
from cumulusci.utils.yaml.cumulusci_yml import ReleaseBranchFormat


def _make_project_config(release_branch_format=None):
    """Create a BaseProjectConfig with optional release_branch_format."""
    config = {
        "project": {
            "package": {"api_version": "64.0"},
            "git": {"release_branch_format": release_branch_format}
            if release_branch_format
            else {},
        }
    }
    return BaseProjectConfig(UniversalConfig(), config=config)


class TestPatternToRegex:
    """Tests for automatic regex compilation from pattern strings."""

    def test_mm_dd(self):
        """Custom pattern mm-dd compiles to correct regex."""
        regex, _ = pattern_to_regex("mm-dd")
        assert regex.match("03-15") is not None
        assert regex.match("12-31") is not None
        assert regex.match("2025-03") is None
        assert regex.match("03-1") is None

    def test_yyyy_mm(self):
        """Lowercase yyyy-mm pattern (tokens are lowercase)."""
        regex, _ = pattern_to_regex("yyyy-mm")
        assert regex.match("2025-03") is not None
        assert regex.match("26-03") is not None
        assert regex.match("2025-13") is not None  # regex allows, validation rejects
        assert regex.match("2025-3") is None

    def test_yyyy(self):
        """yyyy pattern."""
        regex, _ = pattern_to_regex("yyyy")
        assert regex.match("2025") is not None
        assert regex.match("26") is not None
        assert regex.match("2025-03") is None

    def test_fyyyqnsn(self):
        """FYyyQqSn compound pattern (FY, Q, S literal; yy, q, n tokens)."""
        regex, _ = pattern_to_regex("FYyyQqSn")
        assert regex.match("FY26Q3S3") is not None
        assert regex.match("FY26Q1S1") is not None
        assert regex.match("FY26Q5S1") is None  # Q5 invalid
        assert regex.match("FY26Q3S0") is not None  # S0 allowed by regex

    def test_empty_pattern_raises(self):
        """Empty pattern raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            pattern_to_regex("")

    def test_caching(self):
        """Same pattern returns same compiled regex (cached)."""
        r1, _ = pattern_to_regex("mm-dd")
        r2, _ = pattern_to_regex("mm-dd")
        assert r1 is r2

    def test_returns_order(self):
        """pattern_to_regex returns order of matched tokens."""
        _, order = pattern_to_regex("yyyy-mm-dd")
        assert order == ["yyyy", "mm", "dd"]

    def test_pattern_with_literal_only(self):
        """Pattern with only literal characters (no tokens)."""
        regex, order = pattern_to_regex("release")
        assert regex.match("release") is not None
        assert regex.match("2025") is None
        assert order == []

    def test_pattern_yy(self):
        """yy (2-digit year) pattern - matches exactly 2 digits."""
        regex, _ = pattern_to_regex("yy")
        assert regex.match("26") is not None
        assert regex.match("2026") is None  # yy is \d{2}, not 4 digits

    def test_pattern_with_literal_separator(self):
        """Pattern yyyy-mm exercises literal character branch (hyphen)."""
        regex, order = pattern_to_regex("yyyy-mm")
        assert order == ["yyyy", "mm"]
        assert regex.match("2025-03") is not None
        assert regex.match("26-12") is not None


class TestReconstructIdentifierFromGroups:
    """Tests for _reconstruct_identifier_from_groups (literal chars in pattern)."""

    def test_reconstruct_with_literal_separator(self):
        """Pattern yyyy-mm has literal hyphen between tokens."""
        result = _reconstruct_identifier_from_groups(
            "yyyy-mm", {"yyyy": "2025", "mm": "03"}
        )
        assert result == "2025-03"

    def test_reconstruct_fyyyqnsn(self):
        """FYyyQqSn has literals FY, Q, S and tokens yy, q, n."""
        result = _reconstruct_identifier_from_groups(
            "FYyyQqSn", {"yy": "26", "q": "3", "n": "2"}
        )
        assert result == "FY26Q3S2"


class TestParseFormatConfig:
    def test_parse_format_config__default(self):
        assert parse_format_config(None) is None

    def test_parse_format_config__no_format_configured(self):
        project_config = _make_project_config()
        assert parse_format_config(project_config) is None

    def test_parse_format_config__sequential_with_prefix(self):
        project_config = _make_project_config(
            {
                "type": "sequential",
                "prefix": "rel-",
            }
        )
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.type == "sequential"
        assert fmt.prefix == "rel-"
        assert fmt.pattern is None

    def test_parse_format_config__date_yyyy(self):
        project_config = _make_project_config(
            {
                "type": "date",
                "pattern": "yyyy",
            }
        )
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.type == "date"
        assert fmt.pattern == "yyyy"

    def test_parse_format_config__date_yyyy_mm(self):
        project_config = _make_project_config({"type": "date", "pattern": "yyyy-mm"})
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.type == "date"
        assert fmt.pattern == "yyyy-mm"

    def test_parse_format_config__date_yyyy_mm_dd(self):
        project_config = _make_project_config({"type": "date", "pattern": "yyyy-mm-dd"})
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.pattern == "yyyy-mm-dd"

    def test_parse_format_config__date_yyyy_qn(self):
        project_config = _make_project_config({"type": "date", "pattern": "yyyy-Qn"})
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.pattern == "yyyy-Qn"

    def test_parse_format_config__date_yyyy_sprintn(self):
        project_config = _make_project_config(
            {"type": "date", "pattern": "yyyy-Sprintn"}
        )
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.pattern == "yyyy-Sprintn"

    def test_parse_format_config__date_fyyyqnsn(self):
        project_config = _make_project_config(
            {
                "type": "date",
                "pattern": "FYyyQqSn",
                "max_sprints_per_quarter": 4,
            }
        )
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.pattern == "FYyyQqSn"
        assert fmt.max_sprints_per_quarter == 4

    def test_parse_format_config__fyyyqnsn_default_max_sprints(self):
        project_config = _make_project_config({"type": "date", "pattern": "FYyyQqSn"})
        fmt = parse_format_config(project_config)
        assert fmt is not None
        assert fmt.max_sprints_per_quarter == 6

    def test_parse_format_config__max_sprints_none_uses_default(self):
        """Config without max_sprints_per_quarter gets default 6."""
        config = MagicMock()
        config.project__git__release_branch_format__type = "date"
        config.project__git__release_branch_format__prefix = ""
        config.project__git__release_branch_format__pattern = "yyyy-mm"
        config.project__git__release_branch_format__max_sprints_per_quarter = None
        fmt = parse_format_config(config)
        assert fmt is not None
        assert fmt.max_sprints_per_quarter == 6

    def test_parse_format_config__prefix_none_uses_empty(self):
        """Config without prefix gets default empty string."""
        config = MagicMock()
        config.project__git__release_branch_format__type = "sequential"
        config.project__git__release_branch_format__prefix = None
        config.project__git__release_branch_format__pattern = None
        config.project__git__release_branch_format__max_sprints_per_quarter = 6
        fmt = parse_format_config(config)
        assert fmt is not None
        assert fmt.prefix == ""


class TestIsValidReleaseIdentifier:
    def test_sequential__no_prefix(self):
        assert is_valid_release_identifier("230", None) is True
        assert is_valid_release_identifier("0", None) is True
        assert is_valid_release_identifier("rel-230", None) is False
        assert is_valid_release_identifier("abc", None) is False

    def test_sequential__with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert is_valid_release_identifier("rel-230", fmt) is True
        assert is_valid_release_identifier("rel-0", fmt) is True
        assert is_valid_release_identifier("230", fmt) is False
        assert is_valid_release_identifier("rel-abc", fmt) is False

    def test_date_yyyy(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy")
        assert is_valid_release_identifier("2025", fmt) is True
        assert is_valid_release_identifier("26", fmt) is True
        assert is_valid_release_identifier("27", fmt) is True
        assert is_valid_release_identifier("2025-03", fmt) is False

    def test_date_yyyy_mm(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm")
        assert is_valid_release_identifier("2025-03", fmt) is True
        assert is_valid_release_identifier("26-03", fmt) is True
        assert is_valid_release_identifier("2025-13", fmt) is False

    def test_date_yyyy_mm_dd(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm-dd")
        assert is_valid_release_identifier("2025-03-15", fmt) is True
        assert is_valid_release_identifier("26-03-15", fmt) is True
        assert (
            is_valid_release_identifier("2025-02-32", fmt) is False
        )  # dd must be 1-31

    def test_date_yyyy_qn(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        assert is_valid_release_identifier("2025-Q1", fmt) is True
        assert is_valid_release_identifier("26-Q1", fmt) is True
        assert is_valid_release_identifier("2025-Q4", fmt) is True
        assert is_valid_release_identifier("2025-Q5", fmt) is False

    def test_date_yyyy_sprintn(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Sprintn")
        assert is_valid_release_identifier("2025-Sprint1", fmt) is True
        assert is_valid_release_identifier("26-Sprint1", fmt) is True
        assert is_valid_release_identifier("2025-Sprint4", fmt) is True

    def test_date_fyyyqnsn(self):
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert is_valid_release_identifier("FY26Q3S3", fmt) is True
        assert is_valid_release_identifier("FY26Q3S1", fmt) is True
        assert is_valid_release_identifier("FY26Q3S4", fmt) is True
        assert is_valid_release_identifier("FY26Q5S1", fmt) is False
        # Note: n validation only checks >= 0, not <= max_sprints
        assert is_valid_release_identifier("FY26Q3S5", fmt) is True

    def test_date_custom_mm_dd(self):
        """Custom pattern mm-dd validates via pattern_to_regex."""
        fmt = ReleaseBranchFormat(type="date", pattern="mm-dd")
        assert is_valid_release_identifier("03-15", fmt) is True
        assert is_valid_release_identifier("12-31", fmt) is True
        assert is_valid_release_identifier("03-1", fmt) is False
        assert is_valid_release_identifier("3-15", fmt) is False

    def test_date_empty_pattern_returns_false(self):
        """Date format with empty pattern returns False."""
        fmt = ReleaseBranchFormat(type="date", pattern="")
        assert is_valid_release_identifier("2025", fmt) is False

    def test_date_invalid_pattern_returns_false(self):
        """Date format with invalid pattern (ValueError from pattern_to_regex) returns False."""
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm")
        # Valid pattern - test that bad identifier returns False
        assert is_valid_release_identifier("not-a-date", fmt) is False

    def test_unknown_format_type_returns_false(self):
        """Unknown format type returns False."""
        fmt = ReleaseBranchFormat(type="unknown", prefix="", pattern=None)
        assert is_valid_release_identifier("x", fmt) is False


class TestGetReleaseIdentifier:
    def test_sequential__no_prefix(self):
        assert get_release_identifier("feature/230", "feature/", None) == "230"
        assert get_release_identifier("feature/230__test", "feature/", None) == "230"
        assert get_release_identifier("main", "feature/", None) is None
        assert get_release_identifier("feature/abc", "feature/", None) is None

    def test_sequential__with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert get_release_identifier("feature/rel-230", "feature/", fmt) == "rel-230"
        assert (
            get_release_identifier("feature/rel-230__test", "feature/", fmt)
            == "rel-230"
        )

    def test_date_yyyy_q1(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        assert get_release_identifier("feature/2025-Q1", "feature/", fmt) == "2025-Q1"

    def test_date_fyyyqnsn(self):
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_release_identifier("feature/FY26Q3S3", "feature/", fmt) == "FY26Q3S3"
        assert (
            get_release_identifier("feature/FY26Q3S3__test", "feature/", fmt)
            == "FY26Q3S3"
        )

    def test_date_custom_mm_dd(self):
        """Custom pattern mm-dd extracts identifier."""
        fmt = ReleaseBranchFormat(type="date", pattern="mm-dd")
        assert get_release_identifier("feature/03-15", "feature/", fmt) == "03-15"

    def test_prefix_mismatch_returns_none(self):
        """Branch not starting with prefix returns None."""
        assert get_release_identifier("main", "feature/", None) is None
        assert get_release_identifier("release/230", "feature/", None) is None

    def test_invalid_identifier_returns_none(self):
        """Valid prefix but invalid identifier returns None."""
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm")
        assert get_release_identifier("feature/invalid", "feature/", fmt) is None

    def test_empty_identifier_returns_none(self):
        """Branch with only prefix (no identifier) returns None."""
        assert get_release_identifier("feature/", "feature/", None) is None
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm")
        assert get_release_identifier("feature/", "feature/", fmt) is None


class TestGetPreviousIdentifier:
    def test_sequential__default(self):
        assert get_previous_identifier("232", 1, None) == "231"
        assert get_previous_identifier("232", 2, None) == "230"
        assert get_previous_identifier("232", 0, None) == "232"

    def test_sequential__with_prefix(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        assert get_previous_identifier("rel-232", 1, fmt) == "rel-231"
        assert get_previous_identifier("rel-232", 2, fmt) == "rel-230"

    def test_sequential__non_integer_raises(self):
        with pytest.raises(ValueError, match="Cannot compute previous"):
            get_previous_identifier("abc", 1, None)

    def test_sequential__prefix_mismatch_raises(self):
        fmt = ReleaseBranchFormat(type="sequential", prefix="rel-")
        with pytest.raises(ValueError, match="does not match prefix"):
            get_previous_identifier("230", 1, fmt)

    def test_date_yyyy(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy")
        assert get_previous_identifier("2025", 1, fmt) == "2024"
        # yyyy is formatted as 4-digit in output
        assert get_previous_identifier("26", 1, fmt) == "0025"

    def test_date_yyyy_mm(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm")
        assert get_previous_identifier("2025-03", 1, fmt) == "2025-02"
        assert get_previous_identifier("2025-01", 1, fmt) == "2024-12"
        # yyyy is formatted as 4-digit in output
        assert get_previous_identifier("26-03", 1, fmt) == "0026-02"
        assert get_previous_identifier("26-01", 1, fmt) == "0025-12"

    def test_date_yyyy_mm_dd(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-mm-dd")
        assert get_previous_identifier("2025-03-15", 1, fmt) == "2025-03-14"
        # Simple decrement: 01->31 (carry), 03->02 (no calendar awareness)
        assert get_previous_identifier("2025-03-01", 1, fmt) == "2025-02-31"

    def test_date_yyyy_qn(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        assert get_previous_identifier("2025-Q1", 1, fmt) == "2024-Q4"
        assert get_previous_identifier("2025-Q2", 1, fmt) == "2025-Q1"
        assert get_previous_identifier("26-Q1", 1, fmt) == "0025-Q4"
        assert get_previous_identifier("26-Q2", 1, fmt) == "0026-Q1"

    def test_date_yyyy_sprintn(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Sprintn")
        # n token bounds (0,9999): Sprint1->Sprint0 (no quarter rollover)
        assert get_previous_identifier("2025-Sprint1", 1, fmt) == "2025-Sprint0"
        assert get_previous_identifier("2025-Sprint2", 1, fmt) == "2025-Sprint1"

    def test_date_mm_dd(self):
        """mm-dd pattern supports decrement (day, then month)."""
        fmt = ReleaseBranchFormat(type="date", pattern="mm-dd")
        assert get_previous_identifier("03-15", 1, fmt) == "03-14"
        # Simple decrement: 01->31 (carry), 03->02 (no calendar awareness)
        assert get_previous_identifier("03-01", 1, fmt) == "02-31"

    def test_date_fyyyqnsn__same_quarter(self):
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_previous_identifier("FY26Q3S3", 1, fmt) == "FY26Q3S2"
        assert get_previous_identifier("FY26Q3S2", 1, fmt) == "FY26Q3S1"

    def test_date_fyyyqnsn__sprint_decrement(self):
        """FYyyQqSn: S1 decrements to S0 (n bounds 0-9999, no quarter rollover)."""
        fmt = ReleaseBranchFormat(
            type="date", pattern="FYyyQqSn", max_sprints_per_quarter=4
        )
        assert get_previous_identifier("FY26Q3S1", 1, fmt) == "FY26Q3S0"

    def test_date_invalid_identifier_raises(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        with pytest.raises(ValueError, match="Invalid"):
            get_previous_identifier("invalid", 1, fmt)

    def test_unknown_format_type_raises(self):
        fmt = ReleaseBranchFormat(type="unknown", prefix="", pattern=None)
        with pytest.raises(ValueError, match="Unknown format type"):
            get_previous_identifier("x", 1, fmt)

    def test_date_no_pattern_raises(self):
        """Date format without pattern raises Unknown format type (no date path)."""
        fmt = ReleaseBranchFormat(type="date", prefix="", pattern=None)
        with pytest.raises(ValueError, match="Unknown format type"):
            get_previous_identifier("2025", 1, fmt)


class TestConstructReleaseBranchName:
    def test_basic(self):
        assert construct_release_branch_name("feature/", "230") == "feature/230"

    def test_with_prefix_identifier(self):
        assert construct_release_branch_name("feature/", "rel-230") == "feature/rel-230"

    def test_date_format(self):
        assert construct_release_branch_name("feature/", "2025-Q1") == "feature/2025-Q1"
        assert (
            construct_release_branch_name("feature/", "FY26Q3S3") == "feature/FY26Q3S3"
        )


class TestErrorCases:
    def test_fyyyqnsn_invalid_max_sprints(self):
        with pytest.raises(ValueError, match="max_sprints_per_quarter"):
            ReleaseBranchFormat(
                type="date",
                pattern="FYyyQqSn",
                max_sprints_per_quarter=0,
            )

    def test_get_previous_invalid_identifier(self):
        fmt = ReleaseBranchFormat(type="date", pattern="yyyy-Qq")
        with pytest.raises(ValueError, match="Invalid"):
            get_previous_identifier("invalid", 1, fmt)
