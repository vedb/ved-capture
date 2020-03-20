import os
import shutil

import pytest

from install_ved_capture import *


@pytest.fixture()
def output_folder():
    """"""
    folder = os.path.join(os.getcwd(), "out")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


class TestMethods:

    def test_check_ssh_pubkey(self):
        """"""
        assert check_ssh_pubkey() is not None
        assert check_ssh_pubkey("not_a_key") is None

    def test_get_repo_folder(self, output_folder):
        """"""
        assert get_repo_folder(
            output_folder, "ssh://git@github.com/vedb/ved-capture",
        ).endswith("ved-capture")

    def test_clone_repo(self, output_folder):
        """"""
        assert not clone_repo(
            output_folder, "ssh://git@github.com/vedb/wrong_repo",
        )

    def test_install_miniconda(self, output_folder):
        """"""
        install_miniconda(prefix=output_folder)
        assert os.path.exists(os.path.join(output_folder, "bin", "conda"))
