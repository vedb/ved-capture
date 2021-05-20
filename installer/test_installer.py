import sys
import shutil
from pathlib import Path

import pytest

from install_ved_capture import (
    run_command,
    check_ssh_pubkey,
    get_repo_folder,
    get_version_or_branch,
    clone_repo,
    get_min_conda_devenv_version,
    install_miniconda,
)


@pytest.fixture(autouse=True)
def setup():
    """"""
    # maybe not the best solution
    sys.path.append(str(Path.cwd()))


@pytest.fixture()
def output_folder():
    """"""
    folder = Path.cwd() / "out"
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture()
def repo_url():
    """"""
    return "ssh://git@github.com/vedb/ved-capture"


@pytest.fixture()
def local_repo_folder():
    """"""
    return Path(__file__).parents[1]


@pytest.fixture()
def repo_folder(repo_url, output_folder):
    """"""
    folder = output_folder / "ved-capture"
    run_command(["git", "clone", "--depth", "1", repo_url, folder])
    run_command(
        [
            "git",
            f"--work-tree={folder}",
            f"--git-dir={folder}/.git",
            "fetch",
            "--tags",
        ]
    )

    return folder


class TestMethods:
    @pytest.mark.xfail(reason="Fails on GitHub actions")
    def test_check_ssh_pubkey(self):
        """"""
        assert check_ssh_pubkey() is not None
        assert check_ssh_pubkey("not_a_key") is None

    def test_get_repo_folder(self, output_folder):
        """"""
        assert (
            get_repo_folder(
                output_folder, "ssh://git@github.com/vedb/ved-capture",
            ).stem
            == "ved-capture"
        )

    def test_get_version_or_branch(self, repo_folder):
        """"""
        import re

        pattern = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
        assert re.match(pattern, get_version_or_branch(repo_folder))
        assert get_version_or_branch(repo_folder, "devel") == "devel"

    def test_clone_repo(self, output_folder, repo_url):
        """"""
        repo_folder = output_folder / "ved-capture"
        clone_repo(output_folder, repo_folder, repo_url)

        assert (output_folder / "ved-capture" / ".git").exists()

        with pytest.raises(SystemExit):
            clone_repo(
                output_folder,
                repo_folder,
                "ssh://git@github.com/vedb/wrong_repo",
            )

    def test_install_miniconda(self, output_folder):
        """"""
        install_miniconda(prefix=output_folder)
        assert (output_folder / "bin" / "conda").exists()

    @pytest.mark.xfail(reason="environment.devenv.yml was removed")
    def test_get_min_conda_devenv_version(self, local_repo_folder):
        """"""
        version = get_min_conda_devenv_version(local_repo_folder)
        assert version == "2.1.1"
