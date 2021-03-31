import os
from pathlib import Path

import pytest

from ved_capture.config import APPNAME


@pytest.fixture()
def test_data_dir():
    """  Directory containing test data. """
    yield Path(__file__).parent / "test_data"


@pytest.fixture()
def config_dir(test_data_dir):
    """ Directory containing config test files. """
    yield Path(test_data_dir) / "config"


@pytest.fixture()
def user_config_dir(test_data_dir, config_dir):
    """ Directory containing user-specific config test files. """
    user_dir = Path(test_data_dir) / "user_config"
    return user_dir if user_dir.exists() else config_dir


@pytest.fixture(autouse=True)
def set_config_search_path(config_dir):
    """ Override local configuration for tests. """
    os.environ[APPNAME.upper() + "DIR"] = str(config_dir)
