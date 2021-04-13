import inspect
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import click
import oyaml as yaml

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
    "-n",
    "--name",
    default="config",
    help="Name of the config file. Defaults to 'config', i.e. the file will "
    "be called 'config.yaml'.",
)
@click.option(
    "--test_folder",
    default=None,
    help="Recording folder for development testing. Data in this folder will "
    "be overwritten by new recordings. DO NOT SET FOR ACTUAL RECORDINGS!",
)
@click.option(
    "--no_metadata",
    default=False,
    is_flag=True,
    help="Set this flag to skip setting up the default metadata.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def generate_config(folder, name, test_folder, no_metadata, verbose):
    """ Generate configuration. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check folder
    folder = Path(folder or ConfigParser.config_dir()).expanduser()
    if not folder.exists():
        raise_error(f"No such folder: {folder}", logger)
    else:
        logger.debug(f"Saving config file to {folder}")

    # prompt overwrite
    filepath = folder / f"{name}.yaml"
    if filepath.exists():
        answer = input(f"{filepath} exists, overwrite? ([y]/n): ")
        if answer.lower() == "n":
            logger.info(
                f"Did not overwrite {filepath}, use "
                f"'vedc generate_config -n CONFIG_NAME' to generate a config "
                f"with a different name"
            )
            sys.exit(0)

    # create config as defaultdict with arbitrary depth
    # https://stackoverflow.com/a/8702435/4532781
    nested_dict = lambda: defaultdict(nested_dict)  # noqa
    config = nested_dict()

    # get version from default config
    with open(Path(__file__).parents[1] / "config_default.yaml") as f:
        config["version"] = yaml.safe_load(f)["version"]

    # create record config
    config["commands"]["override"] = True
    config["commands"]["record"]["video"] = {}
    config["commands"]["record"]["motion"] = {}
    if test_folder is not None:
        config["commands"]["record"]["folder"] = test_folder
        config["commands"]["record"]["policy"] = "overwrite"
    else:
        config["commands"]["record"][
            "folder"
        ] = "~/recordings/{today:%Y_%m_%d_%H_%M_%S}"
        config["commands"]["record"]["policy"] = "here"
    if no_metadata:
        config["commands"]["record"]["metadata"] = None

    # create estimate_cam_param config
    config["commands"]["estimate_cam_params"][
        "folder"
    ] = "~/pupil_capture_settings"

    # overwrite streams
    config["streams"] = {"override": True, "video": {}, "motion": {}}

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
    for device_name, uid in pupil_devices.items():
        config = get_uvc_config(config, device_name, uid)

    for serial in t265_devices:
        config = get_realsense_config(config, serial)

    for serial in flir_devices:
        config = get_flir_config(config, serial)

    # overwrite profiles
    config["profiles"] = {"override": True}

    # write config
    if len(config["streams"]["video"]) + len(config["streams"]["motion"]) == 0:
        raise_error("No devices selected!", logger)
    else:
        save_config(folder, config, name)


@click.command("auto_config")
@click.option(
    "--test_folder",
    default=None,
    help="Recording folder for development testing. Data in this folder will "
    "be overwritten by new recordings. DO NOT SET FOR ACTUAL RECORDINGS!",
)
@click.option(
    "--no_metadata",
    default=False,
    is_flag=True,
    help="Set this flag to skip setting up the default metadata.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def auto_config(verbose, test_folder, no_metadata):
    """ Auto-generate configuration. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check folder
    folder = Path(ConfigParser.config_dir()).expanduser()
    if not folder.exists():
        raise_error(f"No such folder: {folder}", logger)
    else:
        logger.debug(f"Saving config file to {folder}")

    # prompt overwrite
    filepath = folder / "config.yaml"
    if filepath.exists():
        answer = input(f"{filepath} exists, overwrite? ([y]/n): ")
        if answer.lower() == "n":
            logger.info(f"Did not overwrite {filepath}")
            sys.exit(0)

    # create config as defaultdict with arbitrary depth
    # https://stackoverflow.com/a/8702435/4532781
    nested_dict = lambda: defaultdict(nested_dict)  # noqa
    config = nested_dict()

    # get version from default config
    with open(Path(__file__).parents[1] / "config_default.yaml") as f:
        config["version"] = yaml.safe_load(f)["version"]

    # set test folder if specified
    if test_folder is not None:
        config["commands"]["record"]["folder"] = test_folder
        config["commands"]["record"]["policy"] = "overwrite"

    # get default metadata
    if no_metadata:
        config["commands"]["record"]["metadata"] = None
    else:
        config["commands"]["record"]["metadata"]["study_site"] = input(
            "Please enter the study site (UNR, NDSU, Bates, ...): "
        )
        config["commands"]["record"]["metadata"]["experimenter_id"] = input(
            "Please enter the ID of the experimenter: "
        )

    # get connected devices
    logger.info("Checking connected devices...")
    pupil_devices = get_pupil_devices()
    logger.debug(f"Found pupil cams: {pupil_devices}")
    if len(pupil_devices) not in (2, 3):
        raise_error(
            f"Expected 2 or 3 connected Pupil Core devices, "
            f"found {len(pupil_devices)}"
        )

    t265_devices = get_realsense_devices()
    logger.debug(f"Found T265 devices: {t265_devices}")
    if len(t265_devices) != 1:
        raise_error(
            f"Expected 1 connected T265 device, found {len(t265_devices)}"
        )

    flir_devices = get_flir_devices()
    logger.debug(f"Found FLIR cams: {flir_devices}")
    if len(flir_devices) != 1:
        raise_error(
            f"Expected 1 connected FLIR device, found {len(flir_devices)}"
        )

    # configure devices
    logger.info("Updating config...")

    if "Cam1" in list(pupil_devices.keys())[0]:
        logger.warning(
            "Detected first generation Pupil Core headset, "
            "adapting settings accordingly"
        )
        config["streams"]["video"]["eye0"]["device_uid"] = "Pupil Cam1 ID0"
        config["streams"]["video"]["eye0"]["resolution"] = "(320, 240)"
        config["streams"]["video"]["eye0"]["fps"] = 120
        config["streams"]["video"]["eye0"]["controls"]["Contrast"] = 32
        config["streams"]["video"]["eye1"]["device_uid"] = "Pupil Cam1 ID1"
        config["streams"]["video"]["eye1"]["resolution"] = "(320, 240)"
        config["streams"]["video"]["eye1"]["fps"] = 120
        config["streams"]["video"]["eye1"]["controls"]["Contrast"] = 32
    elif "Cam3" in list(pupil_devices.keys())[0]:
        logger.warning(
            "Detected third generation Pupil Core headset, "
            "adapting settings accordingly"
        )
        config["streams"]["video"]["eye0"]["device_uid"] = "Pupil Cam3 ID0"
        config["streams"]["video"]["eye1"]["device_uid"] = "Pupil Cam3 ID1"

    flir_serial = flir_devices[0]
    config["streams"]["video"]["world"]["device_uid"] = str(flir_serial)

    t265_serial = str(t265_devices[0])
    config["streams"]["video"]["t265"]["device_uid"] = t265_serial
    config["streams"]["motion"]["odometry"]["device_uid"] = t265_serial
    config["streams"]["motion"]["accel"]["device_uid"] = t265_serial
    config["streams"]["motion"]["gyro"]["device_uid"] = t265_serial

    # write config
    save_config(folder, config)
    logger.info("Done!")


@click.command("edit_config")
@click.option(
    "-f",
    "--folder",
    default=None,
    help="Folder where the config file is stored. "
    "Defaults to the application config folder.",
)
@click.option(
    "-n",
    "--name",
    default="config",
    help="Name of the config file. Defaults to 'config', i.e. the file is "
    "called 'config.yaml'.",
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
def edit_config(folder, name, editor, verbose):
    """ Edit configuration. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check file
    folder = Path(folder or ConfigParser.config_dir()).expanduser()
    filepath = folder / f"{name}.yaml"
    if not filepath.exists():
        raise_error(
            f"{filepath} not found, please run 'vedc auto_config' or "
            f"'vedc generate_config' first",
            logger,
        )
    else:
        logger.debug(f"Editing config file {filepath}")

    subprocess.call([editor, str(filepath)])
