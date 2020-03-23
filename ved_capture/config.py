""""""
import os
import datetime
from collections import OrderedDict
from ast import literal_eval

import yaml
from confuse import Configuration, NotFoundError, ConfigTypeError

from pupil_recording_interface.config import VideoConfig, OdometryConfig

APPNAME = "vedc"


class ConfigParser(object):
    def __init__(self, config_file=None):
        """"""
        self.config = Configuration(APPNAME, "ved_capture")

        self.config_file = config_file
        if config_file is not None:
            self.config.set_file(config_file)

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

    def get_policy(self, policy):
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

        return {f: input("{}: ".format(f)) for f in fields}

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
    # TODO save as user_info.csv
    def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwargs):
        """"""
        class OrderedDumper(Dumper):
            pass

        def _dict_representer(dumper, data):
            return dumper.represent_mapping(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                data.items())

        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        return yaml.dump(data, stream, OrderedDumper, **kwargs)

    # save to recording folder
    with open(os.path.join(folder, 'meta.yaml'), 'w') as f:
        ordered_dump(metadata, f)
