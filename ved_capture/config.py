""""""
import os
import datetime
from collections import OrderedDict
from ast import literal_eval
from pathlib import Path
from copy import deepcopy
import csv
import logging

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

    def __init__(self, config_file=None):
        """ Constructor. """
        try:
            self.config = Configuration(APPNAME, "ved_capture")
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

    def get_command_config(self, command, *subkeys):
        """ Get configuration for a CLI command. """
        # TODO user-defined command configs completely
        #  override the package default. Is that what we want?
        try:
            value = deepcopy(self.config["commands"][command].get(dict))
            for key in subkeys:
                value = value[key]
        except KeyError:
            raise NotFoundError(
                f"commands.{command}.{'.'.join(subkeys)} not found"
            )

        return value

    def get_stream_config(self, stream_type, name, *subkeys):
        """ Get config for a stream. """
        # TODO user-defined stream configs completely
        #  override the package default. Is that what we want?
        try:
            value = deepcopy(self.config["streams"][stream_type].get(dict))[
                name
            ]
            for key in subkeys:
                value = value[key]
        except KeyError:
            if len(subkeys):
                raise NotFoundError(
                    f"streams.{name}.{'.'.join(subkeys)} not found"
                )
            else:
                raise NotFoundError(f"Stream '{name}' is not defined")

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

    def get_duration(self, command, duration=None):
        """ Get duration for command. """
        try:
            return duration or self.config["commands"][command][
                "duration"
            ].get(float)
        except (NotFoundError, ConfigTypeError):
            return None

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

    def get_recording_cam_params(self):
        """ Get video streams for which to copy intrinsics and extrinsics. """
        try:
            intrinsics = self.config["commands"]["record"]["intrinsics"].get(
                list
            )
        except (ConfigTypeError, NotFoundError):
            intrinsics = []

        try:
            extrinsics = self.config["commands"]["record"]["extrinsics"].get(
                list
            )
        except (ConfigTypeError, NotFoundError):
            extrinsics = []

        return intrinsics, extrinsics

    def get_metadata(self):
        """ Get recording metadata. """
        try:
            fields = self.config["commands"]["record"]["metadata"].get()
        except NotFoundError:
            return {}

        if isinstance(fields, list):
            return {field: input(f"{field}: ") for field in fields}
        if isinstance(fields, dict):
            return {
                field: (
                    input(f"{field} [{default}]: ")
                    if default is not None
                    else input(f"{field}: ")
                )
                or default
                for field, default in fields.items()
            }
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
        """ Get validation pipelinqe for stream config. """
        if "pipeline" not in config:
            config["pipeline"] = []

        if cam_type == "world":
            config["pipeline"].append(
                pri.CircleDetector.Config(
                    scale=0.5,
                    paused=False,
                    detection_method="vedb",
                    marker_size=(5, 300),
                    threshold_window_size=13,
                    min_area=200,
                    max_area=4000,
                    circularity=0.8,
                    convexity=0.7,
                    inertia=0.4,
                )
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
            name = self.get_command_config("validate", cam_type)
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
            name = self.get_command_config("calibrate", cam_type)
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

    # save to recording folder
    with open(Path(folder) / f"{name}.yaml", "w") as f:
        ordered_dump(OrderedDict(config), f)
