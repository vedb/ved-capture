import pytest

from git.exc import GitError, NoSuchPathError

from ved_capture.utils import (
    get_paths,
    update_repo,
    get_pupil_devices,
    get_realsense_devices,
    get_flir_devices,
    set_profile,
)


class TestUtils:
    def test_get_paths(self, config_dir):
        """"""
        paths = get_paths(config_dir)
        assert paths == {
            "conda_binary": "/usr/share/miniconda/bin/conda",
            "conda_script": "/usr/share/miniconda/etc/profile.d/conda.sh",
            "vedc_repo_folder": "/home/runner/work/ved-capture/ved-capture",
        }

    @pytest.mark.xfail(NoSuchPathError)
    def test_update_repo(self, user_config_dir):
        """"""
        # update once
        update_repo(get_paths(user_config_dir)["vedc_repo_folder"])

        # update again and assert no changes
        assert not update_repo(get_paths(user_config_dir)["vedc_repo_folder"])

        # checkout branch
        update_repo(get_paths(user_config_dir)["vedc_repo_folder"], "devel")
        assert not update_repo(
            get_paths(user_config_dir)["vedc_repo_folder"], "devel"
        )

        # wrong folder
        with pytest.raises(GitError):
            update_repo("not_a_folder")

    def test_get_pupil_devices(self):
        """"""
        # TODO check return value
        get_pupil_devices()

    def test_get_flir_devices(self):
        """"""
        # TODO check return value
        get_flir_devices()

    def test_get_realsense_devices(self):
        """"""
        # TODO check return value
        get_realsense_devices()

    def test_set_profile(self, parser):
        """"""
        # nothing
        metadata = {}
        set_profile(parser, None, metadata)
        assert metadata == {}

        # user specified
        metadata = {}
        set_profile(parser, "indoor", metadata)
        assert metadata["profile"] == "indoor"

        # auto determined from metadata
        metadata = {"lighting": "indoor"}
        set_profile(parser, None, metadata)
        assert metadata["profile"] == "indoor"
