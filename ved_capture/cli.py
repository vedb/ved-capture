""" ``vec_capture.cli`` bundles a variety of command line interfaces. """
import os
import inspect
import importlib
import traceback
import io

import click
from git.exc import GitError
from blessed import Terminal
import pupil_recording_interface as pri

from ved_capture._version import __version__
from ved_capture.cli_utils import (
    init_logger,
    print_log_buffer,
    raise_error,
    get_uvc_config,
    get_realsense_config,
    get_flir_config,
)
from ved_capture.config import (
    ConfigParser,
    save_metadata,
    save_config,
)
from ved_capture.utils import (
    get_paths,
    update_repo,
    update_environment,
    get_pupil_devices,
    get_realsense_devices,
    get_flir_devices,
)


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
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def record(config_file, verbose):
    """ Run recording. """
    t = Terminal()
    f_stdout = io.StringIO()
    logger = init_logger(
        inspect.stack()[0][3],
        verbosity=verbose,
        stream=f_stdout,
        stream_format="[%(levelname)s] %(message)s",
    )

    config_parser = ConfigParser(config_file)
    metadata = config_parser.get_metadata()

    manager = pri.StreamManager(
        config_parser.get_recording_configs(),
        folder=config_parser.get_folder("record", None, **metadata),
        policy=config_parser.get_policy("record"),
    )

    with manager:
        print(
            t.bold(t.turquoise3("Started recording")) + f" to {manager.folder}"
        )
        if len(metadata) > 0:
            save_metadata(manager.folder, metadata)
            logger.debug(f"Saved user_info.csv to {manager.folder}")

        while not manager.stopped:
            print_log_buffer(f_stdout)
            # TODO save position
            if manager.all_streams_running:
                status_str = manager.format_status("fps", max_cols=t.width)
                with t.hidden_cursor():
                    with t.location(0, t.height - 1):
                        print(
                            t.clear_eol
                            + t.bold(t.turquoise3(status_str))
                            + t.move_up
                        )
            else:
                with t.hidden_cursor():
                    with t.location(0, t.height - 1):
                        print(
                            t.clear_eol
                            + t.bold(t.turquoise3("Waiting for init"))
                            + t.move_up
                        )
                    # TODO move to previous position

    # Stop manager
    print(t.clear_eol)
    print_log_buffer(f_stdout)
    with t.location(0, t.height - 1):
        print(t.clear_eol + t.bold(t.firebrick("Stopped recording")))


@click.command("estimate_cam_params")
@click.argument("streams", nargs=-1)
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
@click.option(
    "-e",
    "--extrinsics",
    default=False,
    help="Estimate extrinsics between cameras.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def estimate_cam_params(streams, config_file, extrinsics, verbose):
    """ Estimate camera parameters. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    config_parser = ConfigParser(config_file)

    manager = pri.StreamManager(
        config_parser.get_cam_param_configs(*streams, extrinsics=extrinsics),
        folder=config_parser.get_folder("estimate_cam_params", None),
        policy="here",
    )

    with manager:
        while not manager.stopped:
            if manager.all_streams_running:
                response = input(
                    "Press enter to capture a pattern or type 's' to stop: "
                )
                if response == "s":
                    break
                else:
                    manager.send_notification({"acquire_pattern": True})
                    manager.await_status(streams[0], pattern_acquired=True)

    print("\nStopped")


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
    folder = folder or ConfigParser.config_dir()
    if not os.path.exists(folder):
        raise_error(f"No such folder: {folder}", logger)
    else:
        logger.debug(f"Saving config file to {folder}")

    # default config
    config = {
        "commands": {
            "record": {
                "folder": "~/recordings/{today:%Y_%m_%d}",
                "policy": "new_folder",
                "duration": None,
                "metadata": None,
                "show_video": False,
                "video": {},
                "motion": {},
            }
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


@click.command("update")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
@click.option(
    "-l",
    "--local",
    default=False,
    help="Update from local repository.",
    is_flag=True,
)
@click.option(
    "-s", "--stash", default=False, help="Stash local changes.", count=True,
)
def update(verbose, local, stash):
    """ Update installation. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

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
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def check_install(verbose):
    """ Test installation. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

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
vedc.add_command(estimate_cam_params)
vedc.add_command(generate_config)
vedc.add_command(update)
vedc.add_command(check_install)
