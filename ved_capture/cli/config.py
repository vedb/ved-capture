import inspect
import subprocess
from pathlib import Path

import click
import yaml

from ved_capture.cli.utils import (
    init_logger,
    raise_error,
    get_uvc_config,
    get_realsense_config,
    get_flir_config,
)
from ved_capture.config import ConfigParser, save_config
from ved_capture.utils import (
    get_pupil_devices,
    get_realsense_devices,
    get_flir_devices,
)


@click.command("generate_config")
@click.option(
    "-f",
    "--folder",
    default=None,
    help="Folder where the config file will be stored. "
    "Defaults to the application config folder.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def generate_config(folder, verbose):
    """ Generate configuration. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check folder
    folder = Path(folder or ConfigParser.config_dir()).expanduser()
    if not folder.exists():
        raise_error(f"No such folder: {folder}", logger)
    else:
        logger.debug(f"Saving config file to {folder}")

    # get version from config_default
    with open(Path(__file__).parents[1] / "config_default.yaml") as f:
        version = yaml.safe_load(f)["version"]

    # default config
    config = {
        "version": version,
        "commands": {
            "record": {
                "folder": "~/recordings/{today:%Y_%m_%d_%H_%M_%S}",
                "policy": "here",
                "duration": None,
                "metadata": None,
                "show_video": False,
                "video": {},
                "motion": {},
            },
            "estimate_cam_params": {
                "folder": "~/pupil_capture_settings",
                "streams": {},
            },
            # TODO overwrite with configured streams
            "calibrate": {
                "folder": "~/pupil_capture_settings",
                "world": "world",
                "eye0": "eye0",
                "eye1": "eye1",
            },
        },
        "streams": {"video": {}, "motion": {}},
    }

    # get connected devices
    pupil_devices = get_pupil_devices()
    logger.debug(f"Found pupil cams: {pupil_devices}")

    t265_devices = get_realsense_devices()
    logger.debug(f"Found T265 devices: {t265_devices}")

    flir_devices = get_flir_devices()
    logger.debug(f"Found FLIR cams: {flir_devices}")

    if len(pupil_devices) + len(flir_devices) + len(t265_devices) == 0:
        raise_error("No devices connected!", logger)

    # select devices
    for name, uid in pupil_devices.items():
        config = get_uvc_config(config, name, uid)

    for serial in t265_devices:
        config = get_realsense_config(config, serial)

    for serial in flir_devices:
        config = get_flir_config(config, serial)

    # show video
    config["commands"]["record"]["show_video"] = (
        input("Show video streams during recording? ([y]/n): ").lower() != "n"
    )

    # write config
    if len(config["streams"]["video"]) + len(config["streams"]["motion"]) == 0:
        raise_error("No devices selected!", logger)
    else:
        save_config(folder, config)


@click.command("edit_config")
@click.option(
    "-f",
    "--folder",
    default=None,
    help="Folder where the config file is stored. "
    "Defaults to the application config folder.",
)
@click.option(
    "-e",
    "--editor",
    default="nano",
    help="Editor to use for editing. Defaults to 'nano'.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def edit_config(folder, editor, verbose):
    """ Edit configuration. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check file
    folder = Path(folder or ConfigParser.config_dir()).expanduser()
    filepath = folder / "config.yaml"
    if not filepath.exists():
        raise_error(
            f"{filepath} not found, please run 'vedc generate_config' first",
            logger,
        )
    else:
        logger.debug(f"Editing config file {filepath}")

    subprocess.call([editor, str(filepath)])
