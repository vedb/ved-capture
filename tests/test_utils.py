import pytest

from git.exc import GitError

from ved_capture.utils import get_paths, update_repo


class TestUtils:
    def test_get_paths(self, config_dir):
        """"""
        paths = get_paths(config_dir)
        assert paths == {
            "conda_binary": "/usr/share/miniconda/bin/conda",
            "conda_script": "/usr/share/miniconda/etc/profile.d/conda.sh",
            "vedc_repo_folder": "/home/runner/work/ved-capture/ved-capture",
        }

    def test_update_repo(self, user_config_dir):
        """"""
        # update once
        update_repo(get_paths(user_config_dir)["vedc_repo_folder"])

        # update again and assert no changes
        assert not update_repo(get_paths(user_config_dir)["vedc_repo_folder"])

        # wrong folder
        with pytest.raises(GitError):
            update_repo("not_a_folder")
