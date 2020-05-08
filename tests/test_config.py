import os

import pytest

from ved_capture.config import ConfigParser


class TestConfigParser(object):
    @pytest.fixture()
    def config_file(self, config_dir):
        """"""
        yield os.path.join(config_dir, "config.yaml")

    @pytest.fixture()
    def parser(self, config_file):
        """"""
        yield ConfigParser(config_file)

    def test_constructor(self, config_file):
        """"""
        parser = ConfigParser(config_file)
        assert (
            parser.config["streams"]["video"]["t265"]["device_type"].get()
            == "t265"
        )

        parser = ConfigParser()
        assert (
            parser.config["commands"]["record"]["metadata"].get()[0]
            == "location"
        )

    def test_get_folder(self, parser, config_dir):
        """"""
        import datetime

        folder = parser.get_folder("record", None)
        assert folder == f"{config_dir}/out/{datetime.date.today():%Y-%m-%d}"

    def test_get_policy(self, parser):
        """"""
        # test config file
        assert parser.get_policy("record") == "overwrite"
        # user override
        assert parser.get_policy("record", "here") == "here"
        # package default
        assert ConfigParser().get_policy("record") == "new_folder"

    def test_get_show_video(self, parser):
        """"""
        # test config file
        assert parser.get_show_video()
        # user override
        assert not parser.get_show_video(False)
        # package default
        assert ConfigParser().get_show_video()

    def test_get_metadata(self, parser, monkeypatch):
        """"""
        monkeypatch.setattr("builtins.input", lambda x: "000")
        assert parser.get_metadata() == {"subject_id": "000"}

    def test_get_recording_configs(self, parser):
        """"""
        # TODO add __eq__ to Config to handle equality check
        config_list = parser.get_recording_configs()

        assert config_list[0].stream_type == "video"
        assert config_list[0].device_type == "t265"
        assert config_list[0].resolution == (1696, 800)
        assert config_list[0].pipeline[0].process_type == "video_recorder"
        assert config_list[0].pipeline[1].process_type == "video_display"

        assert config_list[1].stream_type == "motion"
        assert config_list[1].device_type == "t265"
        assert config_list[1].pipeline[0].process_type == "motion_recorder"

    def test_get_calibration_configs(self, parser):
        """"""
        config_list = parser.get_calibration_configs()

        assert config_list[0].stream_type == "video"
        assert config_list[0].pipeline[0].process_type == "circle_detector"
        assert config_list[0].pipeline[1].process_type == "calibration"
        assert config_list[0].pipeline[2].process_type == "gaze_mapper"
        assert config_list[0].pipeline[3].process_type == "video_display"

        assert config_list[1].stream_type == "video"
        assert config_list[1].pipeline[0].process_type == "pupil_detector"
        assert config_list[1].pipeline[1].process_type == "video_display"

        assert config_list[2].stream_type == "video"
        assert config_list[2].pipeline[0].process_type == "pupil_detector"
        assert config_list[2].pipeline[1].process_type == "video_display"

    def test_get_cam_param_configs(self, parser):
        """"""
        config_list = parser.get_cam_param_configs("world", "t265")

        assert config_list[0].stream_type == "video"
        assert (
            config_list[0].pipeline[0].process_type == "circle_grid_detector"
        )
        assert config_list[0].pipeline[1].process_type == "cam_param_estimator"
        assert config_list[0].pipeline[2].process_type == "video_display"

        assert config_list[1].device_type == "t265"
        assert (
            config_list[1].pipeline[0].process_type == "circle_grid_detector"
        )
        assert config_list[1].pipeline[1].process_type == "video_display"

    def test_get_show_configs(self, parser):
        """"""
        config_list = parser.get_show_configs("world", "t265")

        assert config_list[0].stream_type == "video"
        assert config_list[0].pipeline[0].process_type == "video_display"

        assert config_list[1].device_type == "t265"
        assert config_list[1].pipeline[0].process_type == "video_display"
