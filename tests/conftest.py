import os

import pytest

from ved_capture.config import APPNAME


@pytest.fixture()
def test_data_dir():
    yield os.path.join(os.path.dirname(__file__), 'test_data')


@pytest.fixture(autouse=True)
def set_config_search_path():
    """"""
    # assuming test dir does not contain a config file...
    os.environ[APPNAME.upper() + 'DIR'] = os.path.dirname(__file__)
