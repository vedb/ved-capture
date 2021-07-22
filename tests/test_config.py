from pathlib import Path

import pytest
from confuse import NotFoundError

from ved_capture.config import ConfigParser, flatten, save_config


class TestConfigParser:
    def test_constructor(self, config_dir, config_file):
        """"""
        # path to file
        parser = ConfigParser(config_file)
        assert (
            parser.config["streams"]["video"]["t265"]["device_uid"].get()
            == "t265"
        )

        # package default
        parser = ConfigParser(ignore_user=True)
        assert (
            parser.config["streams"]["video"]["t265"]["device_uid"].get()
            is None
        )

        # config file by name
        parser = ConfigParser("config_minimal")
        assert (
            parser.config["commands"]["record"]["metadata"]["study_site"].get()
            == "test_site"
        )

    def test_get_stream_config(self, parser, parser_override):
        """"""
        # single updated value
        assert parser.get_stream_config("video", "eye0", "fps") == 200

        # whole dict
        assert set(parser.get_stream_config("video", "eye0").keys()) == {
            "device_type",
            "device_uid",
            "resolution",
            "fps",
            "color_format",
            "exposure_mode",
            "controls",
        }

        # override
        assert set(
            parser_override.get_stream_config("video", "t265").keys()
        ) == {
            "device_type",
            "device_uid",
            "resolution",
            "fps",
            "color_format",
        }

    def test_get_command_config(self, parser, parser_override):
        """"""
        # single updated value
        assert parser.get_command_config("record", "policy") == "overwrite"

        # whole dict
        assert set(parser.get_command_config("record", "motion").keys()) == {
            "odometry",
            "accel",
            "gyro",
        }

        # override
        assert set(parser_override.get_command_config("record").keys()) == {
            "video",
            "motion",
            "folder",
            "policy",
        }

    def test_set_profile(self, parser):
        """"""
        parser.set_profile("outdoor")
        assert (
            parser.get_stream_config("video", "eye0", "controls", "Gamma")
            == 10
        )

        with pytest.raises(NotFoundError):
            parser.set_profile("not_a_profile")

    def test_get_folder(
        self, parser, parser_minimal, parser_override, config_dir
    ):
        """"""
        import datetime

        # with metadata
        folder = parser.get_folder("record", subject_id="000")
        assert folder == config_dir.parent / "out" / "recordings" / "000"

        # minimal config / package default
        folder = parser_minimal.get_folder("record")
        assert (
            folder
            == Path.home()
            / "recordings"
            / f"{datetime.datetime.today():%Y_%m_%d_%H_%M_%S}"
        )

        # override
        folder = parser_override.get_folder("record")
        assert folder == Path.home() / "recordings" / "vedc_test"

        # user specified
        folder = parser.get_folder("record", folder=config_dir)
        assert folder == config_dir

    def test_get_policy(self, parser, parser_minimal, parser_override):
        """"""
        # test config file
        assert parser.get_policy("record") == "overwrite"
        # minimal/package default
        assert parser_minimal.get_policy("record") == "here"
        # override
        assert parser_override.get_policy("record") == "overwrite"
        # user specified
        assert parser.get_policy("record", "new_folder") == "new_folder"

    def test_get_show_video(self, parser, parser_minimal):
        """"""
        # test config file
        assert parser.get_show_video()
        # minimal/package default
        assert not parser_minimal.get_show_video()
        # user specified
        assert not parser.get_show_video(False)

    def test_get_recording_cam_params(self, parser_minimal):
        """"""
        # minimal/package default
        assert parser_minimal.get_recording_cam_params() == (
            ["world"],
            ["world", "t265"],
        )

    def test_get_metadata(self, parser, parser_override, monkeypatch):
        """"""
        # as list
        monkeypatch.setattr("builtins.input", lambda x: "000")
        assert parser.get_metadata() == {"subject_id": "000"}

        # as dict with default
        parser.config["commands"]["record"]["metadata"] = {"subject_id": "000"}
        monkeypatch.setattr("builtins.input", lambda x: "")
        assert parser.get_metadata() == {"subject_id": "000"}
        monkeypatch.setattr("builtins.input", lambda x: "001")
        assert parser.get_metadata() == {"subject_id": "001"}

        # override
        assert parser_override.get_metadata() == {}

    def test_get_recording_configs(self, parser):
        """"""
        # TODO add __eq__ to Config to handle equality check
        config_list = parser.get_recording_configs()

        assert config_list[0].stream_type == "video"
        assert config_list[0].device_type == "flir"
        assert config_list[0].device_uid == "flir"
        assert config_list[0].resolution == (2048, 1536)
        assert config_list[0].pipeline[0].process_type == "video_recorder"
        assert config_list[0].pipeline[1].process_type == "video_display"

        assert config_list[1].fps == 200
        assert config_list[2].fps == 200

        assert config_list[4].stream_type == "motion"
        assert config_list[4].device_type == "t265"
        assert config_list[4].device_uid == "t265"
        assert config_list[4].pipeline[0].process_type == "motion_recorder"

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

    def test_get_validation_configs(self, parser):
        """"""
        config_list = parser.get_validation_configs()

        assert config_list[0].stream_type == "video"
        assert (
            config_list[0].pipeline[0].process_type == "circle_detector_vedb"
        )
        assert config_list[0].pipeline[0].min_area == 200
        # TODO assert config_list[0].pipeline[1].process_type == "validation"
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
        config_list = parser.get_cam_param_configs(
            "world", "t265", extrinsics=True
        )

        assert config_list[0].stream_type == "video"
        assert (
            config_list[0].pipeline[0].process_type == "circle_grid_detector"
        )
        assert config_list[0].pipeline[1].process_type == "cam_param_estimator"
        assert config_list[0].pipeline[1].extrinsics
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


class TestMethods:
    def test_flatten(self, parser, parser_override):
        """"""
        config = flatten(parser.config)
        assert config["streams"]["video"]["eye0"]["fps"] == 200

        config = flatten(parser_override.config)
        assert set(config["commands"].keys()) == {
            "override",
            "record",
            "estimate_cam_params",
            "validate",
            "calibrate",
        }
        assert set(config["streams"]["video"].keys()) == {"t265"}

    def test_save_config(self, tmpdir, parser, parser_override):
        """"""
        # dict
        save_config(tmpdir, {})

        # config
        save_config(tmpdir, parser.config)

        # override config
        save_config(tmpdir, parser_override.config)
