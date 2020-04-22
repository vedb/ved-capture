""""""
import os
import datetime
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
    """ Parser for application config. """

    def __init__(self, config_file=None):
        """ Constructor. """
        self.config = Configuration(APPNAME, "ved_capture")

        self.config_file = config_file
        if config_file is not None:
            self.config.set_file(config_file)
            logger.debug(f"Loaded configuration from {config_file}")

    def get_command_config(self, command, *subkeys):
        """ Get configuration for a CLI command. """
        # TODO user-defined command configs completely
        #  override the package default. Is that what we want?
        value = self.config["commands"][command].get(dict)
        for key in subkeys:
            value = value[key]
        return value

    def get_stream_config(self, stream_type, name, *subkeys):
        """ Get config for a CLI command. """
        # TODO user-defined stream configs completely
        #  override the package default. Is that what we want?
        value = self.config["streams"][stream_type].get(dict)[name]
        for key in subkeys:
            value = value[key]
        return value

    @classmethod
    def config_dir(cls):
        """ Directory for user configuration. """
        return Configuration(APPNAME, "ved_capture").config_dir()

    def get_folder(self, command, folder, **metadata):
        """ Resolve folder for command. """
        if folder is not None:
            return folder

        try:
            folder = self.config["commands"][command].get(dict)["folder"]
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

    def get_policy(self, command, policy=None):
        """ Get policy for command. """
        try:
            return policy or self.config["commands"][command]["policy"].get(
                str
            )
        except (NotFoundError, ConfigTypeError):
            return "new_folder"

    def get_show_video(self, show_video=None):
        """ Get show_video flag. """
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
        """ Get recording metadata. """
        try:
            fields = self.config["commands"]["record"]["metadata"].get(list)
        except (NotFoundError, ConfigTypeError):
            return {}

        if fields is not None:
            return {f: input("{}: ".format(f)) for f in fields}
        else:
            return {}

    def _get_recording_pipeline(self, config, name, stream_type):
        """ Get recording pipeline for stream config. """
        recorder_types = {
            "video": pri.VideoRecorder.Config,
            "motion": pri.MotionRecorder.Config,
        }

        if "pipeline" not in config:
            config["pipeline"] = []

        command_config = self.get_command_config("record", stream_type, name)
        config["pipeline"].append(
            recorder_types[stream_type](**(command_config or {}))
        )
        if self.get_show_video() and stream_type == "video":
            config["pipeline"].append(pri.VideoDisplay.Config())

        return config

    def get_recording_configs(self):
        """ Get list of configurations for recording. """
        configs = []

        for name in self.get_command_config("record", "video") or {}:
            config = self.get_stream_config("video", name)
            config["resolution"] = literal_eval(config["resolution"])
            config = self._get_recording_pipeline(config, name, "video")
            configs.append(pri.VideoStream.Config(name=name, **config))
            logger.debug(
                f"Adding video stream '{name}' with config: {dict(config)}"
            )

        for name in self.get_command_config("record", "motion") or {}:
            config = self.get_stream_config("motion", name)
            config = self._get_recording_pipeline(config, name, "motion")
            configs.append(pri.MotionStream.Config(name=name, **config))
            logger.debug(
                f"Adding motion stream '{name}' with config: {dict(config)}"
            )

        return configs

    def _get_cam_param_pipeline(
        self, config, name, streams, master, extrinsics=False
    ):
        """ Get camera parameter estimator pipeline for stream config. """
        if "pipeline" not in config:
            config["pipeline"] = []

        command_config = self.get_command_config(
            "estimate_cam_params", "streams", name
        )
        config["pipeline"].append(
            pri.CircleGridDetector.Config(**(command_config or {}))
        )
        if master:
            # first stream gets cam param estimator
            config["pipeline"].append(
                pri.CamParamEstimator.Config(
                    streams=streams, extrinsics=extrinsics
                )
            )
        config["pipeline"].append(
            pri.VideoDisplay.Config(overlay_circle_grid=True)
        )

        return config

    def get_cam_param_configs(self, *streams, extrinsics=False):
        """ Get list of configurations for estimating camera parameters. """
        configs = []

        # TODO num_patterns

        for idx, name in enumerate(streams):
            config = self.get_stream_config("video", name)
            config["resolution"] = literal_eval(config["resolution"])
            config = self._get_cam_param_pipeline(
                config or {}, name, streams, idx == 0, extrinsics
            )
            configs.append(pri.VideoStream.Config(name=name, **config))

        return configs


def save_metadata(folder, metadata):
    """ Save metadata to user_info.csv. """
    with open(os.path.join(folder, "user_info.csv"), "w") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        w.writerows(metadata.items())


def save_config(folder, config):
    """ Save configuration to config.yaml. """

    def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
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
