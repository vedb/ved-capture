""" ``vec_capture.cli`` bundles a variety of command line interfaces. """
import os
import logging
import inspect
import importlib
import traceback

import click
from git.exc import GitError
from pupil_recording_interface import (
    MultiStreamRecorder,
    VideoDeviceUVC,
)

from ved_capture._version import __version__
from ved_capture.config import (
    ConfigParser,
    save_metadata,
    save_config,
    get_uvc_config,
    get_realsense_config,
)
from ved_capture.utils import (
    get_paths,
    update_repo,
    update_environment,
    get_serial_numbers,
)


def init_logger(subcommand, verbose=False):
    """ Initialize logger with file and stream handler for a subcommand. """
    # root logger with file handler
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(name)s | %(levelname)s: %(message)s",
        filename=os.path.join(
            ConfigParser().config.config_dir(), "vedc." + subcommand + ".log"
        ),
    )

    # stream handler
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler = logging.StreamHandler()
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(stream_formatter)

    # add the handler to the root logger
    logging.getLogger("").addHandler(stream_handler)

    return logging.getLogger("vedc." + subcommand)


def raise_error(msg, logger=None):
    """ Log error as debug message and raise ClickException. """
    if logger is not None:
        logger.debug(f"ERROR: {msg}")

    raise click.ClickException(msg)


@click.group("vedc")
@click.version_option(version=__version__)
def vedc():
    """ Visual Experience Data Capture.

    Command line tool for the Visual Experience Database.
    """


@click.command("record")
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
def record(config_file, verbose):
    """ Run recording. """
    logger = init_logger(inspect.stack()[0][3], verbose=verbose)

    config_parser = ConfigParser(config_file)
    logger.debug("Parsed config")

    metadata = config_parser.get_metadata()

    recorder = MultiStreamRecorder(
        config_parser.get_recording_folder(None, **metadata),
        config_parser.get_recording_configs(),
        show_video=True,
    )

    if len(metadata) > 0:
        save_metadata(recorder.folder, metadata)
        logger.debug(f"Saved user_info.csv to {recorder.folder}")

    # TODO use curses for this
    for fps_dict in recorder.run():
        fps_str = recorder.format_fps(fps_dict)
        if fps_str is not None:
            print("\rSampling rates: " + fps_str, end="")


@click.command("generate_config")
@click.option(
    "-f",
    "--folder",
    default=None,
    help="Folder where the config file will be stored. "
    "Defaults to the application config folder.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
def generate_config(folder, verbose):
    """ Generate recording configuration. """
    logger = init_logger(inspect.stack()[0][3], verbose=verbose)

    # check folder
    folder = folder or ConfigParser.config_dir()
    if not os.path.exists(folder):
        raise_error(f"No such folder: {folder}", logger)
    else:
        logger.debug(f"Saving config file to {folder}")

    # default config
    config = {
        "record": {
            "folder": "~/recordings/{today:%Y_%m_%d}",
            "policy": "new_folder",
            "duration": None,
            "metadata": None,
        },
        "video": {},
        "odometry": {},
    }

    # get connected devices
    pupil_cams = {
        name: uid
        for name, uid in VideoDeviceUVC._get_connected_device_uids().items()
        if name.startswith("Pupil Cam")
    }
    logger.debug(f"Found pupil cams: {pupil_cams}")

    realsense_cams = get_serial_numbers()
    logger.debug(f"Found realsense cams: {realsense_cams}")

    # TODO
    flir_cams = {}
    logger.debug(f"Found FLIR cams: {flir_cams}")

    if len(pupil_cams) + len(flir_cams) + len(realsense_cams) == 0:
        raise_error("No devices connected!", logger)

    # select devices
    for name, uid in pupil_cams.items():
        config = get_uvc_config(config, name, uid)

    for serial in realsense_cams:
        config = get_realsense_config(config, serial)

    # write config
    if len(config["video"]) + len(config["odometry"]) == 0:
        raise_error("No devices selected!", logger)
    else:
        save_config(folder, config)


@click.command("update")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
@click.option(
    "-l",
    "--local",
    default=False,
    help="Update from local repository.",
    is_flag=True,
)
@click.option(
    "-s", "--stash", default=False, help="Stash local changes.", is_flag=True,
)
def update(verbose, local, stash):
    """ Update installation. """
    logger = init_logger(inspect.stack()[0][3], verbose=verbose)

    paths = get_paths()
    if paths is None:
        raise_error(
            "Application paths have not been set up. You might need to "
            "reinstall.",
            logger,
        )

    # update repo if needed
    if not local:
        logger.info(f"Updating {paths['vedc_repo_folder']}")
        try:
            update_repo(paths["vedc_repo_folder"], stash)
        except GitError as e:
            raise_error(f"Repository update failed. Reason: {str(e)}", logger)

    # update environment
    logger.info("Updating environment.\nThis will take a couple of minutes. ☕")
    return_code = update_environment(
        paths["conda_binary"],
        paths["conda_script"],
        paths["vedc_repo_folder"],
        local=local,
    )
    if return_code != 0:
        raise_error("Environment update failed", logger)


@click.command("check_install")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
def check_install(verbose):
    """ Test installation. """
    logger = init_logger(inspect.stack()[0][3], verbose=verbose)

    failures = []

    def check_import(module):
        try:
            importlib.import_module(module)
        except ImportError:
            logger.error(f"Could not import {module}.")
            logger.debug(traceback.format_exc())
            failures.append(module)

    for module in ["uvc", "PySpin", "pyrealsense2"]:
        check_import(module)

    if len(failures) == 0:
        logger.info("Installation check OK.")
    else:
        raise_error("Installation check failed!", logger)


# add subcommands
vedc.add_command(record)
vedc.add_command(generate_config)
vedc.add_command(update)
vedc.add_command(check_install)
