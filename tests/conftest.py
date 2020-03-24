import os

import pytest

from ved_capture.config import APPNAME


@pytest.fixture()
def test_data_dir():
    """  Directory containing test data. """
    yield os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture()
def config_dir(test_data_dir):
    """ Directory containing config test files. """
    yield os.path.join(test_data_dir, "config")


@pytest.fixture()
def user_config_dir(test_data_dir, config_dir):
    """ Directory containing user-specific config test files. """
    user_dir = os.path.join(test_data_dir, "user_config")
    return user_dir if os.path.exists(user_dir) else config_dir


@pytest.fixture(autouse=True)
def set_config_search_path():
    """ Override local configuration for tests. """
    # assuming test dir does not contain a config file...
    os.environ[APPNAME.upper() + "DIR"] = os.path.dirname(__file__)
