"""Tests for validators."""

from utils.validators import validate_raw_thought


def test_validate_raw_thought_valid():
    valid, err = validate_raw_thought("This is a sufficiently long raw thought about AI agents.")
    assert valid is True
    assert err is None


def test_validate_raw_thought_too_short():
    valid, err = validate_raw_thought("Short")
    assert valid is False
    assert "too short" in err


def test_validate_raw_thought_empty():
    valid, err = validate_raw_thought("")
    assert valid is False
    assert "too short" in err


def test_validate_raw_thought_whitespace_only():
    valid, err = validate_raw_thought("     \n\n   ")
    assert valid is False
    assert "too short" in err
