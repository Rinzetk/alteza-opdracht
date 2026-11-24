"""Dummy-test: het package is te importeren."""

import gh_commits


def dummy_test_package_has_version():
    assert gh_commits.__version__ == "0.1.0"
