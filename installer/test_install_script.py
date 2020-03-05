import shutil

import pytest

from installer.install_ved_capture import *


@pytest.fixture()
def base_folder():
    """"""
    folder = os.path.join(os.getcwd(), "out")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


class TestMethods:

    def test_check_ssh_pubkey(self):
        """"""
        assert check_ssh_pubkey() is not None
        assert check_ssh_pubkey("not_a_key") is None

    def test_get_repo_folder(self, base_folder):
        """"""
        assert get_repo_folder(
            base_folder, "ssh://git@github.com/vedb/ved-capture"
        ).endswith("ved-capture")

    def test_clone_repo(self, base_folder):
        """"""
        assert not clone_repo(
            base_folder, "ssh://git@github.com/vedb/wrong_repo"
        )[0]
