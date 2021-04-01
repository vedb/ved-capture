""""""
import csv
import datetime
import logging
import os
from ast import literal_eval
from collections import OrderedDict, defaultdict
from copy import deepcopy
from distutils.version import StrictVersion
from pathlib import Path

import yaml
from confuse import (
    Configuration,
    NotFoundError,
    ConfigTypeError,
    ConfigReadError,
)
import pupil_recording_interface as pri

APPNAME = "vedc"

# maximum width of video windows
MAX_WIDTH = 1280

logger = logging.getLogger(__name__)


class ConfigParser:
    """ Parser for application config. """

    def __init__(self, config_file=None, ignore_user=False):
        """ Constructor. """
        try:
            self.config = Configuration(APPNAME, "ved_capture", read=False)
        except ConfigReadError as e:
            from ved_capture.cli.utils import raise_error

            raise_error(str(e), logger)

        if config_file is not None:
            if str(config_file).endswith(".yaml"):
                self.config_file = config_file
            else:
                self.config_file = (
                    Path(self.config.config_dir()) / f"{config_file}.yaml"
                )
            self.config.set_file(self.config_file)
            logger.debug(f"Loaded configuration from {config_file}")
        else:
            self.config_file = None

        # ignore user config if config file provided or explicitly ignored
        if config_file is not None or ignore_user:
            self.config.read(user=False)
        else:
            self.config.read()

        # check if legacy format (user-defined config overrides all defaults)
        self.legacy = (
            StrictVersion(self.config["version"].get(str)).version[0] < 2
        )
        if self.legacy:
            logger.warning(
                "You are using an outdated config file format, "
                "run 'vedc auto_config' to update"
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if exc_type is not None:
            from ved_capture.cli.utils import raise_error

            logger.debug(exc_val, exc_info=True)
            raise_error(
                f"Could not parse configuration ({exc_type.__name__}): "
                f"{exc_val}",
                logger,
            )

    @classmethod
    def config_dir(cls):
        """ Directory for user configuration. """
        return Configuration(APPNAME, "ved_capture").config_dir()

    def _get_config(self, category, subcategory, *subkeys, datatype=None):
        """ Get config value. """
        try:
            override = self.config[category]["override"].get(bool)
        except (ConfigTypeError, NotFoundError):
            override = False

        # override/legacy mode: user-defined config overrides defaults
        if override or self.legacy:
            try:
                value = deepcopy(self.config[category][subcategory].get(dict))
                for key in subkeys:
                    value = value[key]
                return value
            except KeyError:
                raise NotFoundError(
                    f"{'.'.join([category, subcategory] + list(subkeys))} "
                    f"not found"
                )

        # new mode: merge data from all config sources
        value = self.config[category][subcategory]
        for key in subkeys:
            value = value[key]

        # raise error if value isn't defined anywhere
        if not value.exists():
            raise NotFoundError(
                f"{'.'.join([category, subcategory] + list(subkeys))} "
                f"not found"
            )

        if datatype is None:
            try:
                # if dict, merge data from all config sources
                return value.flatten()
            except ConfigTypeError:
                # not a dict, just return the value
                return value.get()
        else:
            return value.get(datatype)

    def set_profile(self, profile):
        """ Set a stream profile. """
        settings = self._get_config("profiles", profile)
        self.config["streams"].set(settings)

    def get_command_config(self, command, *subkeys, datatype=None):
        """ Get configuration for a CLI command. """
        return self._get_config(
            "commands", command, *subkeys, datatype=datatype
        )

    def get_stream_config(self, stream_type, name, *subkeys, datatype=None):
        """ Get configuration for a stream. """
        return self._get_config(
            "streams", stream_type, name, *subkeys, datatype=datatype
        )

    def get_folder(self, command, folder=None, **metadata):
        """ Resolve folder for command. """
        if folder is not None:
            return folder

        try:
            folder = self.get_command_config(command, "folder", datatype=str)
            if folder is not None:
                try:
                    folder = folder.format(
                        cwd=os.getcwd(),
                        cfgd=os.path.dirname(
                            self.config_file or self.config.config_dir()
                        ),
                        today=datetime.datetime.today(),
                        **metadata,
                    )
                    return Path(folder).expanduser()
                except KeyError as e:
                    raise ValueError(
                        f"Format spec in commands.{command}.folder requires "
                        f"{e} to be defined in commands.{command}.metadata"
                    )
            else:
                return Path.cwd()
        except NotFoundError:
            return Path.cwd()

    def get_policy(self, command, policy=None):
        """ Get policy for command. """
        try:
            return policy or self.get_command_config(
                command, "policy", datatype=str
            )
        except NotFoundError:
            return "new_folder"

    def get_duration(self, command, duration=None):
        """ Get duration for command. """
        try:
            return duration or self.get_command_config(command, "duration")
        except NotFoundError:
            return None

    def get_show_video(self, show_video=None):
        """ Get show_video flag. """
        if show_video is None:
            try:
                return self.get_command_config(
                    "record", "show_video", datatype=bool
                )
            except NotFoundError:
                return False
        else:
            return show_video

    def get_recording_cam_params(self):
        """ Get video streams for which to copy intrinsics and extrinsics. """
        try:
            intrinsics = self.get_command_config(
                "record", "intrinsics", datatype=list
            )
        except NotFoundError:
            intrinsics = []

        try:
            extrinsics = self.get_command_config(
                "record", "extrinsics", datatype=list
            )
        except NotFoundError:
            extrinsics = []

        return intrinsics, extrinsics

    def get_metadata(self):
        """ Get recording metadata. """
        try:
            fields = self.get_command_config("record", "metadata")
        except NotFoundError:
            return {}

        if isinstance(fields, list):
            print("Please enter the following metadata:")
            metadata = {field: input(f"- {field}: ") for field in fields}
            print("")
            return metadata
        if isinstance(fields, (OrderedDict, dict)):
            print(
                "Please enter the following metadata (press Enter to accept "
                "default values in square brackets):"
            )
            metadata = {
                field: (
                    input(f"- {field} [{default}]: ")
                    if default is not None
                    else input(f"- {field}: ")
                )
                or default
                for field, default in fields.items()
            }
            print("")
            return metadata
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
        if stream_type == "video":
            config["pipeline"].append(
                pri.VideoDisplay.Config(
                    max_width=MAX_WIDTH, paused=not self.get_show_video()
                )
            )

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

    def _get_validation_pipeline(self, config, cam_type):
        """ Get validation pipeline for stream config. """
        if "pipeline" not in config:
            config["pipeline"] = []

        if cam_type == "world":
            try:
                circle_detector_params = self.get_command_config(
                    "validate", "settings", "circle_detector"
                )
            except NotFoundError:
                circle_detector_params = {}

            config["pipeline"].append(
                pri.CircleDetector.Config(**circle_detector_params)
            )
            config["pipeline"].append(pri.Validation.Config(save=True))
            config["pipeline"].append(pri.GazeMapper.Config())
            config["pipeline"].append(
                pri.VideoDisplay.Config(max_width=MAX_WIDTH)
            )
        elif cam_type == "eye0":
            config["pipeline"].append(pri.PupilDetector.Config())
            config["pipeline"].append(pri.VideoDisplay.Config(flip=True))
        elif cam_type == "eye1":
            config["pipeline"].append(pri.PupilDetector.Config())
            config["pipeline"].append(pri.VideoDisplay.Config())

        return config

    def get_validation_configs(self):
        """ Get list of configurations for validation. """
        configs = []

        for cam_type in ("world", "eye0", "eye1"):
            name = self.get_command_config("validate", cam_type, datatype=str)
            config = self.get_stream_config("video", name)
            config["resolution"] = literal_eval(config["resolution"])
            config = self._get_validation_pipeline(config or {}, cam_type)
            configs.append(pri.VideoStream.Config(name=name, **config))

        return configs

    def _get_calibration_pipeline(self, config, cam_type):
        """ Get calibration pipeline for stream config. """
        if "pipeline" not in config:
            config["pipeline"] = []

        if cam_type == "world":
            config["pipeline"].append(pri.CircleDetector.Config(paused=True))
            config["pipeline"].append(pri.Calibration.Config(save=True))
            config["pipeline"].append(pri.GazeMapper.Config())
            config["pipeline"].append(
                pri.VideoDisplay.Config(max_width=MAX_WIDTH)
            )
        elif cam_type == "eye0":
            config["pipeline"].append(pri.PupilDetector.Config())
            config["pipeline"].append(pri.VideoDisplay.Config(flip=True))
        elif cam_type == "eye1":
            config["pipeline"].append(pri.PupilDetector.Config())
            config["pipeline"].append(pri.VideoDisplay.Config())

        return config

    def get_calibration_configs(self):
        """ Get list of configurations for calibration. """
        configs = []

        for cam_type in ("world", "eye0", "eye1"):
            name = self.get_command_config("calibrate", cam_type, datatype=str)
            config = self.get_stream_config("video", name)
            config["resolution"] = literal_eval(config["resolution"])
            config = self._get_calibration_pipeline(config or {}, cam_type)
            configs.append(pri.VideoStream.Config(name=name, **config))

        return configs

    def _get_cam_param_pipeline(
        self, config, name, streams, master, extrinsics=False
    ):
        """ Get camera parameter estimator pipeline for stream config. """
        if "pipeline" not in config:
            config["pipeline"] = []

        try:
            command_config = self.config["commands"]["estimate_cam_params"][
                "streams"
            ][name].get(dict)
        except (ConfigTypeError, NotFoundError):
            command_config = {}

        config["pipeline"].append(
            pri.CircleGridDetector.Config(**command_config)
        )
        if master:
            # first stream gets cam param estimator
            config["pipeline"].append(
                pri.CamParamEstimator.Config(
                    streams=streams, extrinsics=extrinsics
                )
            )
        config["pipeline"].append(pri.VideoDisplay.Config(max_width=MAX_WIDTH))

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

    def get_show_configs(self, *streams):
        """ Get list of configurations for showing camera streams. """
        configs = []

        for idx, name in enumerate(streams):
            config = self.get_stream_config("video", name)
            config["resolution"] = literal_eval(config["resolution"])
            config["pipeline"] = [pri.VideoDisplay.Config()]
            configs.append(pri.VideoStream.Config(name=name, **config))

        return configs


def save_metadata(folder, metadata):
    """ Save metadata to user_info.csv. """
    with open(os.path.join(folder, "user_info.csv"), "w") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        w.writerows(metadata.items())


def default_to_regular(d):
    """ Convert nested defaultdict to nested regular dict. """
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


def save_config(folder, config, name="config"):
    """ Save configuration to yaml file. """

    def ordered_dump(data, stream=None, Dumper=yaml.Dumper, **kwds):
        class OrderedDumper(Dumper):
            pass

        def _dict_representer(dumper, data):
            return dumper.represent_mapping(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items()
            )

        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        return yaml.dump(data, stream, OrderedDumper, **kwds)

    # convert defaultdicts to regular dicts
    config = default_to_regular(config)

    # save to recording folder
    with open(Path(folder) / f"{name}.yaml", "w") as f:
        ordered_dump(OrderedDict(config), f)
