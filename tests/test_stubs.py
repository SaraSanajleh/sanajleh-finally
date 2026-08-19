"""Tests for future extension point stubs."""

from app.core.stubs import assert_protocols


def test_extension_stubs_satisfy_protocols() -> None:
    assert_protocols()
