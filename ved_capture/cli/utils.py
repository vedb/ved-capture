""""""
import logging
import os
import pprint
import sys

import click
import pupil_recording_interface as pri

from ved_capture.config import ConfigParser, logger


def init_logger(
    subcommand, verbosity=0, stream=sys.stdout, stream_format="%(message)s"
):
    """ Initialize logger with file and stream handler for a subcommand. """
    TRACE = 5

    # root logger with file handler
    logging.basicConfig(
        level=TRACE,
        format="%(asctime)s | %(name)s | %(levelname)s: %(message)s",
        filename=os.path.join(
            ConfigParser().config.config_dir(), "vedc." + subcommand + ".log"
        ),
    )
    logging.addLevelName(TRACE, "TRACE")
    verbosity_map = {
        0: logging.INFO,
        1: logging.DEBUG,
        2: TRACE,
    }

    # stream handler
    stream_formatter = logging.Formatter(stream_format)
    stream_handler = logging.StreamHandler(stream)
    stream_handler.setLevel(verbosity_map[int(verbosity)])
    stream_handler.setFormatter(stream_formatter)

    # add the handler to the root logger
    root_logger = logging.getLogger("")
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(verbosity_map[int(verbosity)])

    return logging.getLogger("vedc." + subcommand)


def flush_log_buffer(stream):
    """ Flush buffered logs. """
    stream.flush()
    buffer = stream.getvalue()
    stream.truncate(0)
    if len(buffer):
        return buffer.rstrip("\n")


def print_log_buffer(stream):
    """ Print buffered logs. """
    buffer = flush_log_buffer(stream)
    if buffer:
        print(buffer)


def raise_error(msg, logger=None):
    """ Log error as debug message and raise ClickException. """
    if logger is not None:
        logger.debug(f"ERROR: {msg}")

    raise click.ClickException(msg)


def setup_stream_prompt(device_type, device_uid, stream_type):
    """ Ask the user whether they want to set up a stream. """
    choice = input(
        f"Found {device_type} device '{device_uid}'\n"
        f"Do you want to set up {stream_type} streaming for this device? "
        f"([y]/n): "
    )
    if choice.lower() == "n":
        logger.warning(
            f"Skipping {stream_type} setup for device '{device_uid}'"
        )
        return False
    else:
        return True


def stream_name_prompt(config, default):
    """ Ask the user for the name of the stream. """
    stream_name = (
        input(
            f"Enter stream name or press Enter to use the name '{default}': "
        )
        or default
    )
    if stream_name in config:
        logger.error(
            f"Stream name {stream_name} already exists, please make a "
            f"different choice"
        )
        return stream_name_prompt(config, default)
    else:
        return stream_name


def fps_prompt(default):
    """ Ask the user for the desired fps. """
    try:
        choice = (
            input(f"Enter FPS or press enter to set to {default}: ") or default
        )
        return float(choice)
    except ValueError:
        logger.error("Invalid FPS, please try again.")
        return fps_prompt(default)


def record_prompt(config, stream_type, stream_name):
    """ Ask the user whether they want to record a stream. """
    choice = input("Do you want to record this stream? ([y]/n): ")
    if choice.lower() != "n":
        if stream_type not in config["commands"]["record"]:
            config["commands"]["record"][stream_type] = {}
        if stream_type == "video":
            config["commands"]["record"][stream_type][stream_name] = {
                "codec": "libx264",
                "encoder_kwargs": {"crf": "18", "preset": "ultrafast"},
            }
        else:
            config["commands"]["record"][stream_type][stream_name] = None


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

    if setup_stream_prompt("pupil", name, "video"):
        stream_name = stream_name_prompt(
            config["streams"]["video"], stream_name
        )
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
            "color_format": "gray"
            if stream_name.startswith("eye")
            else "bgr24",
        }
        record_prompt(config, "video", stream_name)
        config["commands"]["estimate_cam_params"]["streams"][
            stream_name
        ] = None

    return config


def get_realsense_config(
    config, serial, device_type="t265", fps=30, resolution=(1696, 800)
):
    """ Get config for a RealSense device. """
    # video
    if setup_stream_prompt(device_type, serial, "video"):
        stream_name = stream_name_prompt(
            config["streams"]["video"], device_type
        )
        config["streams"]["video"][stream_name] = {
            "resolution": str(resolution),
            "fps": fps,
            "device_type": device_type,
            "device_uid": serial,
            "color_format": "gray",
        }
        record_prompt(config, "video", stream_name)
        config["commands"]["estimate_cam_params"]["streams"][stream_name] = {
            "stereo": True
        }

    # motion
    for motion_type in ("odometry", "accel", "gyro"):
        if setup_stream_prompt(device_type, serial, motion_type):
            stream_name = stream_name_prompt(
                config["streams"]["motion"], motion_type
            )
            config["streams"]["motion"][stream_name] = {
                "device_type": device_type,
                "device_uid": serial,
                "motion_type": motion_type,
            }
            record_prompt(config, "motion", stream_name)

    return config


def get_flir_config(
    config, serial, device_type="flir", resolution=(2048, 1536)
):
    """ Get config for a FLIR camera. """
    if setup_stream_prompt(device_type, serial, "video"):
        stream_name = stream_name_prompt(
            config["streams"]["video"], device_type
        )
        config["streams"]["video"][stream_name] = {
            "resolution": str(resolution),  # TODO get from cam
            "fps": fps_prompt(30.0),  # TODO get default from cam
            "device_type": device_type,
            "device_uid": serial,
            "color_format": "bayer_rggb8",
            "settings": {
                "GainAuto": "Continuous",
                "ExposureAuto": "Continuous",
            },
        }
        record_prompt(config, "video", stream_name)
        config["commands"]["estimate_cam_params"]["streams"][
            stream_name
        ] = None

    return config
