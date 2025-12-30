"""Example test file to verify test setup works"""

import pytest
from kiro_budget import __version__


def test_version():
    """Test that version is defined"""
    assert __version__ == "0.1.0"


def test_example():
    """Example test case"""
    assert 1 + 1 == 2