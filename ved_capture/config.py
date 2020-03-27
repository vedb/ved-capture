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
from pupil_recording_interface import VideoDeviceUVC
from pupil_recording_interface.config import VideoConfig, OdometryConfig

APPNAME = "vedc"

logger = logging.getLogger(__name__)


class ConfigParser(object):
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
            folder = self.config["record"]["folder"].get()
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
        except (NotFoundError, ConfigTypeError):
            return os.getcwd()

    def get_policy(self, policy=None):
        """"""
        try:
            return policy or self.config["record"]["policy"].get()
        except ConfigTypeError:
            return "new_folder"

    def get_metadata(self):
        """"""
        try:
            fields = self.config["record"]["metadata"].get()
        except ConfigTypeError:
            return None

        if fields is not None:
            return {f: input("{}: ".format(f)) for f in fields}
        else:
            return {}

    def get_recording_configs(self):
        """"""
        configs = []

        if self.config["video"].get() is not None:
            for name, config in self.config["video"].get(dict).items():
                config["resolution"] = literal_eval(config["resolution"])
                configs.append(VideoConfig(name=name, **config))

        if self.config["odometry"].get() is not None:
            for name, config in self.config["odometry"].get(dict).items():
                configs.append(OdometryConfig(name=name, **config))

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
        device_name = "eye0"
    elif name.endswith("ID1"):
        device_name = "eye1"
    elif name.endswith("ID2"):
        device_name = "world"
    else:
        device_name = name

    choice = input(
        f"Found device '{name}'.\n"
        f"Do you want to set up video recording for this device? [y/n]: "
    )

    if choice != "y":
        logger.warning(f"Skipping device '{name}'")
        return config

    device_name = (
        input(
            f"Enter device name or press Enter to use the name "
            f"'{device_name}': "
        )
        or device_name
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
        for idx, mode in enumerate(VideoDeviceUVC._get_available_modes(uid))
    }

    selected_mode = mode_prompt(modes)

    config["video"][device_name] = {
        "device_type": "uvc",
        "device_uid": name,
        "resolution": str(selected_mode[:-1]),
        "fps": selected_mode[-1],
        "color_format": "gray" if device_name.startswith("eye") else "bgr24",
        "codec": "libx264",
    }

    return config


def get_realsense_config(config, serial, device_name="t265"):
    """ Get config for a RealSense device. """
    # video
    choice = input(
        f"Found T265 device with serial number '{serial}'.\n"
        f"Do you want to set up video recording for this device [y/n]: "
    )

    if choice != "y":
        logger.warning(f"Skipping video setup for device '{serial}'")
    else:
        device_name = (
            input(
                f"Enter device name or press Enter to use the name "
                f"'{device_name}': "
            )
            or device_name
        )
        config["video"][device_name] = {
            "resolution": "(1696, 800)",
            "fps": 30,
            "codec": "libx264",
            "device_type": "t265",
            "device_uid": serial,
            "color_format": "gray",
        }

    # odometry
    choice = input(
        f"Do you want to set up odometry recording for this device [y/n]: "
    )

    if choice != "y":
        logger.warning(f"Skipping odometry setup for device '{serial}'")
    else:
        device_name = (
            input(
                f"Enter device name or press Enter to use the name "
                f"'{device_name}': "
            )
            or device_name
        )
        config["odometry"][device_name] = {
            "device_type": "t265",
            "device_uid": serial,
        }

    return config
