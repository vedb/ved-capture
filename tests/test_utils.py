from ved_capture.utils import (
    get_pupil_devices,
    get_realsense_devices,
    get_flir_devices,
    set_profile,
)


class TestUtils:
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
