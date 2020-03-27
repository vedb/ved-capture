""" ``vec_capture.cli`` bundles a variety of command line interfaces. """
import os
import sys
import logging
import inspect
import importlib
import traceback
from contextlib import contextmanager
import ctypes
import io
import tempfile

import click
from git.exc import GitError
from blessed import Terminal
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


libc = ctypes.CDLL(None)
c_stdout = ctypes.c_void_p.in_dll(libc, "stdout")


@contextmanager
def redirect(stream):
    # The original fd stdout points to. Usually 1 on POSIX systems.
    original_stdout_fd = sys.stdout.fileno()

    def _redirect_stdout(to_fd):
        """Redirect stdout to the given file descriptor."""
        # Flush the C-level buffer stdout
        libc.fflush(c_stdout)
        # Flush and close sys.stdout - also closes the file descriptor (fd)
        sys.stdout.close()
        # Make original_stdout_fd point to the same file as to_fd
        os.dup2(to_fd, original_stdout_fd)
        # Create a new sys.stdout that points to the redirected fd
        sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, "wb"))

    # Save a copy of the original stdout fd in saved_stdout_fd
    saved_stdout_fd = os.dup(original_stdout_fd)
    try:
        # Create a temporary file and redirect stdout to it
        tfile = tempfile.TemporaryFile(mode="w+b")
        _redirect_stdout(tfile.fileno())
        # Yield to caller, then redirect stdout back to the saved fd
        yield
        _redirect_stdout(saved_stdout_fd)
        # Copy contents of temporary file to the given stream
        tfile.flush()
        tfile.seek(0, io.SEEK_SET)
        stream.write(tfile.read().decode())
    finally:
        try:
            tfile.close()
        except UnboundLocalError:
            pass
        os.close(saved_stdout_fd)


def init_logger(subcommand, verbose=False, stream=sys.stdout):
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
    stream_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    stream_handler = logging.StreamHandler(stream)
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(stream_formatter)

    # add the handler to the root logger
    logging.getLogger("").addHandler(stream_handler)

    return logging.getLogger("vedc." + subcommand)


def print_log_buffer(stream):
    """ Print buffered logs. """
    stream.flush()
    buffer = stream.getvalue()
    stream.truncate(0)
    if len(buffer):
        print(buffer)


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
    t = Terminal()
    f_stdout = io.StringIO()
    logger = init_logger(
        inspect.stack()[0][3], verbose=verbose, stream=f_stdout
    )

    config_parser = ConfigParser(config_file)

    metadata = config_parser.get_metadata()

    recorder = MultiStreamRecorder(
        config_parser.get_recording_folder(None, **metadata),
        config_parser.get_recording_configs(),
        policy=config_parser.get_policy(),
        show_video=config_parser.get_show_video(),
    )

    if len(metadata) > 0:
        save_metadata(recorder.folder, metadata)
        logger.debug(f"Saved user_info.csv to {recorder.folder}")

    # Start recorder
    recorder.start()
    print(t.bold(t.turquoise3("Started recording")) + f" to {recorder.folder}")

    fps_generator = recorder.spin()
    while True:
        try:
            fps_str = recorder.format_fps(next(iter(fps_generator)))
            print_log_buffer(f_stdout)
            with t.hidden_cursor():
                with t.location(0, t.height - 1):
                    if fps_str is not None:
                        print(
                            t.clear_eol
                            + t.bold(
                                t.turquoise3("Sampling rates: ") + fps_str
                            )
                            + t.move_up
                        )
                    else:
                        print(
                            t.clear_eol
                            + t.bold(t.turquoise3("Waiting for init"))
                            + t.move_up
                        )
        except (StopIteration, KeyboardInterrupt):
            break

    # Stop recorder
    recorder.stop()
    print(t.clear_eol)
    print_log_buffer(f_stdout)
    with t.location(0, t.height - 1):
        print(t.clear_eol + t.bold(t.firebrick("Stopped recording")))


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
            "show_video": False,
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

    # show video
    config["record"]["show_video"] = input(
        "Show video streams during recording? [y/n]: "
    ) == "y"

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
