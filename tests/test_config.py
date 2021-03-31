from pathlib import Path

import pytest

from ved_capture.config import ConfigParser


class TestConfigParser:
    @pytest.fixture()
    def config_file(self, config_dir):
        """ Path to the test config file. """
        yield Path(config_dir) / "config.yaml"

    @pytest.fixture()
    def parser(self):
        """ Parser with test config. """
        yield ConfigParser()

    @pytest.fixture()
    def parser_default(self):
        """ Parser with default config. """
        yield ConfigParser(ignore_user=True)

    @pytest.fixture()
    def parser_minimal(self, config_dir):
        """ Parser with minimal config (standard user config). """
        yield ConfigParser(Path(config_dir) / "config_minimal.yaml")

    @pytest.fixture()
    def parser_override(self, config_dir):
        """ Parser with overriding config (e.g. from generate_config). """
        yield ConfigParser(Path(config_dir) / "config_override.yaml")

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

    def test_get_folder(self, parser, parser_minimal, config_dir):
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
        folder = parser.get_folder("record", folder=config_dir)
        assert folder == config_dir

    def test_get_policy(self, parser, parser_minimal):
        """"""
        # test config file
        assert parser.get_policy("record") == "overwrite"
        # user override
        assert parser.get_policy("record", "new_folder") == "new_folder"
        # minimal/package default
        assert parser_minimal.get_policy("record") == "here"

    def test_get_show_video(self, parser, parser_minimal):
        """"""
        # test config file
        assert parser.get_show_video()
        # user override
        assert not parser.get_show_video(False)
        # minimal/package default
        assert not parser_minimal.get_show_video()

    def test_get_recording_cam_params(self, parser_minimal):
        """"""
        # minimal/package default
        assert parser_minimal.get_recording_cam_params() == (
            ["world"],
            ["world", "t265"],
        )

    def test_get_metadata(self, parser, monkeypatch):
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

    def test_get_recording_configs(self, parser):
        """"""
        # TODO add __eq__ to Config to handle equality check
        config_list = parser.get_recording_configs()

        assert config_list[0].stream_type == "video"
        assert config_list[0].device_type == "flir"
        assert config_list[0].resolution == (2048, 1536)
        assert config_list[0].pipeline[0].process_type == "video_recorder"
        assert config_list[0].pipeline[1].process_type == "video_display"

        assert config_list[4].stream_type == "motion"
        assert config_list[4].device_type == "t265"
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
        assert config_list[0].pipeline[0].process_type == "circle_detector"
        assert config_list[0].pipeline[0].min_area == 200
        assert config_list[0].pipeline[1].process_type == "validation"
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
