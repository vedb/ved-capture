import os

import pytest

from pupil_recording_interface.config import VideoConfig, OdometryConfig

from ved_capture.config import ConfigParser


class TestConfigParser(object):
    @pytest.fixture()
    def config_file(self, test_data_dir):
        """"""
        yield os.path.join(test_data_dir, "config.yaml")

    @pytest.fixture()
    def parser(self, config_file):
        """"""
        yield ConfigParser(config_file)

    def test_constructor(self, config_file):
        """"""
        parser = ConfigParser(config_file)
        assert parser.config["video"]["t265"]["device_type"].get() == "t265"

        parser = ConfigParser()
        assert parser.config["record"]["metadata"].get()[0] == "location"

    def test_get_recording_folder(self, parser, test_data_dir):
        """"""
        import datetime

        folder = parser.get_recording_folder(None)
        assert folder == "{dir}/out/{today:%Y-%m-%d}".format(
            dir=test_data_dir, today=datetime.date.today()
        )

    def test_get_policy(self, parser):
        """"""
        assert parser.get_policy(None) == "overwrite"
        assert parser.get_policy("here") == "here"

    def test_get_metadata(self, parser, monkeypatch):
        """"""
        monkeypatch.setattr("builtins.input", lambda x: "000")
        assert parser.get_metadata() == {"subject_id": "000"}

    def test_get_recording_configs(self, parser):
        """"""
        # TODO add __eq__ to pri.StreamConfig to handle equality check
        config_list = parser.get_recording_configs()
        assert isinstance(config_list[0], VideoConfig)
        assert config_list[0].device_type == "t265"
        assert config_list[0].resolution == (1696, 800)
        assert isinstance(config_list[1], OdometryConfig)
        assert config_list[1].device_type == "t265"
