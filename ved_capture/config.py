""""""
import os
import datetime
import pprint
from collections import OrderedDict
from ast import literal_eval
import csv
import logging

import yaml
from confuse import Configuration, NotFoundError, ConfigTypeError
import pupil_recording_interface as pri

APPNAME = "vedc"

logger = logging.getLogger(__name__)


class ConfigParser(object):
    """"""

    def __init__(self, config_file=None):
        """"""
        self.config = Configuration(APPNAME, "ved_capture")

        self.config_file = config_file
        if config_file is not None:
            self.config.set_file(config_file)
            logger.debug(f"Loaded configuration from {config_file}")

    @classmethod
    def config_dir(cls):
        """"""
        return Configuration(APPNAME, "ved_capture").config_dir()

    def set_args(self, args, command=None):
        """"""
        if command is None:
            self.config.set_args(args)
        else:
            self.config[command].set_args(args)

    def get_args(self, command=None):
        """"""
        if command is None:
            return self.config.get()
        else:
            return self.config[command].get()

    def get_recording_folder(self, folder, **metadata):
        """"""
        if folder is not None:
            return folder

        try:
            folder = self.config["commands"]["record"].get(dict)["folder"]
            if folder is not None:
                try:
                    return folder.format(
                        cwd=os.getcwd(),
                        cfgd=os.path.dirname(
                            self.config_file or self.config.config_dir()
                        ),
                        today=datetime.datetime.today(),
                        **metadata,
                    )
                except KeyError as e:
                    raise ValueError(
                        f"Invalid folder config: '{e}' is missing in metadata"
                    )
            else:
                return os.getcwd()
        except (NotFoundError, ConfigTypeError, KeyError):
            return os.getcwd()

    def get_policy(self, policy=None):
        """"""
        try:
            return policy or self.config["commands"]["record"]["policy"].get(
                str
            )
        except (NotFoundError, ConfigTypeError):
            return "new_folder"

    def get_show_video(self, show_video=None):
        """"""
        if show_video is None:
            try:
                return self.config["commands"]["record"]["show_video"].get(
                    bool
                )
            except (NotFoundError, ConfigTypeError):
                return False
        else:
            return show_video

    def get_metadata(self):
        """"""
        try:
            fields = self.config["commands"]["record"]["metadata"].get(list)
        except (NotFoundError, ConfigTypeError):
            return {}

        if fields is not None:
            return {f: input("{}: ".format(f)) for f in fields}
        else:
            return {}

    def _get_recording_pipeline(self, config_dict, name, stream_type):
        """"""
        recorder_types = {
            "video": pri.VideoRecorder.Config,
            "motion": pri.MotionRecorder.Config,
        }

        try:
            record_config = self.config["commands"]["record"].get(dict)[
                stream_type
            ][name]
        except (NotFoundError, ConfigTypeError, KeyError):
            return config_dict

        if "pipeline" not in config_dict:
            config_dict["pipeline"] = []

        config_dict["pipeline"].append(
            recorder_types[stream_type](**(record_config or {}))
        )

        if self.get_show_video() and stream_type == "video":
            config_dict["pipeline"].append(pri.VideoDisplay.Config())

        return config_dict

    def get_recording_configs(self):
        """"""
        # TODO turn this around by parsing record first and devices after?
        # TODO user-defined stream and recording configs completely
        #  override the package default. Is that what we want?
        configs = []

        if self.config["streams"]["video"].get() is not None:
            for name, config in (
                self.config["streams"]["video"].get(dict).items()
            ):
                config["resolution"] = literal_eval(config["resolution"])
                config = self._get_recording_pipeline(config, name, "video")
                configs.append(pri.VideoStream.Config(name=name, **config))
                logger.debug(
                    f"Adding video device '{name}' with config: {dict(config)}"
                )

        if self.config["streams"]["motion"].get() is not None:
            for name, config in (
                self.config["streams"]["motion"].get(dict).items()
            ):
                config = self._get_recording_pipeline(config, name, "motion")
                configs.append(pri.MotionStream.Config(name=name, **config))
                logger.debug(
                    f"Adding motion device '{name}' with config: "
                    f"{dict(config)}"
                )

        return configs


def save_metadata(folder, metadata):
    """"""
    with open(os.path.join(folder, "user_info.csv"), "w") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        w.writerows(metadata.items())


def save_config(folder, config):
    """"""

    def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
        """"""

        class OrderedDumper(Dumper):
            pass

        def _dict_representer(dumper, data):
            return dumper.represent_mapping(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items()
            )

        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        return yaml.dump(data, stream, OrderedDumper, **kwds)

    # save to recording folder
    with open(os.path.join(folder, "config.yaml"), "w") as f:
        ordered_dump(OrderedDict(config), f)


def get_uvc_config(config, name, uid):
    """ Get config for a Pupil UVC cam. """
    if name.endswith("ID0"):
        stream_name = "eye0"
    elif name.endswith("ID1"):
        stream_name = "eye1"
    elif name.endswith("ID2"):
        stream_name = "world"
    else:
        stream_name = name

    choice = input(
        f"Found device '{name}'.\n"
        f"Do you want to set up video streaming for this device? ([y]/n): "
    )

    if choice.lower() == "n":
        logger.warning(f"Skipping device '{name}'")
        return config

    stream_name = (
        input(
            f"Enter stream name or press Enter to use the name "
            f"'{stream_name}': "
        )
        or stream_name
    )

    def mode_prompt(modes):
        try:
            choice = input(
                f"Please select a capture mode "
                f"(horizontal res, vertical res, fps):\n"
                f" {pprint.pformat(modes).strip('{}')}\n"
                f"Selection: "
            )
            return modes[int(choice)]
        except (ValueError, KeyError):
            logger.error("Invalid choice, please try again.")
            return mode_prompt(modes)

    modes = {
        idx: mode
        for idx, mode in enumerate(
            pri.VideoDeviceUVC._get_available_modes(uid)
        )
    }

    selected_mode = mode_prompt(modes)

    config["streams"]["video"][stream_name] = {
        "device_type": "uvc",
        "device_uid": name,
        "resolution": str(selected_mode[:-1]),
        "fps": selected_mode[-1],
        "color_format": "gray" if stream_name.startswith("eye") else "bgr24",
    }

    choice = input("Do you want to record this stream? ([y]/n): ")
    if choice.lower() != "n":
        if "video" not in config["commands"]["record"]:
            config["commands"]["record"]["video"] = {}
        config["commands"]["record"]["video"][stream_name] = None

    return config


def get_realsense_config(config, serial, device_name="t265"):
    """ Get config for a RealSense device. """
    # video
    choice = input(
        f"Found T265 device with serial number '{serial}'.\n"
        f"Do you want to set up video streaming for this device ([y]/n): "
    )
    if choice.lower() == "n":
        logger.warning(f"Skipping video setup for device '{serial}'")
    else:
        stream_name = (
            input(
                f"Enter stream name or press Enter to use the name "
                f"'{device_name}': "
            )
            or device_name
        )
        config["streams"]["video"][stream_name] = {
            "resolution": "(1696, 800)",
            "fps": 30,
            "device_type": "t265",
            "device_uid": serial,
            "color_format": "gray",
        }
        choice = input("Do you want to record this stream? ([y]/n): ")
        if choice.lower() != "n":
            if "video" not in config["commands"]["record"]:
                config["commands"]["record"]["video"] = {}
            config["commands"]["record"]["video"][stream_name] = None

    # motion
    for motion_type in ("odometry", "accel", "gyro"):
        choice = input(
            f"Do you want to set up {motion_type} streaming for this device "
            f"([y]/n): "
        )
        if choice.lower() == "n":
            logger.warning(
                f"Skipping {motion_type} setup for device '{serial}'"
            )
        else:
            stream_name = (
                input(
                    f"Enter stream name or press Enter to use the name "
                    f"'{motion_type}': "
                )
                or motion_type
            )
            config["streams"]["motion"][stream_name] = {
                "device_type": "t265",
                "device_uid": serial,
                "motion_type": motion_type,
            }
            choice = input("Do you want to record this stream? ([y]/n): ")
            if choice.lower() != "n":
                if "motion" not in config["commands"]["record"]:
                    config["commands"]["record"]["motion"] = {}
                config["commands"]["record"]["motion"][stream_name] = None

    return config
