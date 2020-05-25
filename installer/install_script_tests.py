import os
import shutil

import pytest

from install_ved_capture import (
    run_command,
    check_ssh_pubkey,
    get_repo_folder,
    get_version_or_branch,
    clone_repo,
    install_miniconda,
)


@pytest.fixture()
def output_folder():
    """"""
    folder = os.path.join(os.getcwd(), "out")
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture()
def repo_url():
    """"""
    return "ssh://git@github.com/vedb/ved-capture"


@pytest.fixture()
def repo_folder(repo_url, output_folder):
    """"""
    folder = os.path.join(output_folder, "ved-capture")
    run_command(["git", "clone", "--depth", "1", repo_url, folder])

    return folder


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

    def test_get_version_or_branch(self, repo_folder):
        """"""
        assert get_version_or_branch(repo_folder).startswith("v")
        assert get_version_or_branch(repo_folder, "devel") == "devel"

    def test_clone_repo(self, output_folder, repo_url):
        """"""
        repo_folder = os.path.join(output_folder, "ved-capture")
        clone_repo(output_folder, repo_folder, repo_url)

        assert os.path.exists(
            os.path.join(output_folder, "ved-capture", ".git")
        )

        with pytest.raises(SystemExit):
            clone_repo(
                output_folder,
                repo_folder,
                "ssh://git@github.com/vedb/wrong_repo",
            )

    def test_install_miniconda(self, output_folder):
        """"""
        install_miniconda(prefix=output_folder)
        assert os.path.exists(os.path.join(output_folder, "bin", "conda"))
