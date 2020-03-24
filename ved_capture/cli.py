""" ``vec_capture.cli`` bundles a variety of command line interfaces. """
import logging
import inspect
import importlib
import traceback

import click
from git.exc import GitError

from pupil_recording_interface import MultiStreamRecorder

from ved_capture._version import __version__
from ved_capture.config import ConfigParser, save_metadata
from ved_capture.utils import get_paths, update_repo, update_environment
from ved_capture import utils


def init_logger(subcommand, verbose=False):
    """"""
    logger = logging.getLogger(__name__ + ":" + subcommand)
    logger.setLevel(logging.DEBUG)

    # stream handler
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler = logging.StreamHandler()
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    # TODO this can be done more elegantly
    utils.logger = logger

    return logger


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
    logger = init_logger(str(inspect.currentframe()), verbose=verbose)

    config_parser = ConfigParser(config_file)

    metadata = config_parser.get_metadata()

    recorder = MultiStreamRecorder(
        config_parser.get_recording_folder(None, **metadata),
        config_parser.get_recording_configs(),
        show_video=True,
    )

    save_metadata(recorder.folder, metadata)
    recorder.run()


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
    logger = init_logger(str(inspect.currentframe()), verbose=verbose)

    paths = get_paths()
    if paths is None:
        raise click.ClickException(
            "Application paths have not been set up. You might need to "
            "reinstall."
        )

    # update repo if needed
    if not local:
        logger.info(f"Updating {paths['vedc_repo_folder']}")
        try:
            update_repo(paths["vedc_repo_folder"], stash)
        except GitError as e:
            raise click.ClickException(
                f"Repository update failed. Reason: {str(e)}"
            )

    # update environment
    logger.info("Updating environment.\nThis will take a couple of minutes. ☕")
    return_code = update_environment(
        paths["conda_binary"],
        paths["conda_script"],
        paths["vedc_repo_folder"],
        local=local,
    )
    if return_code != 0:
        raise click.ClickException("Environment update failed")


@click.command("check_install")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
def check_install(verbose):
    """ Test installation. """
    logger = init_logger(str(inspect.currentframe()), verbose=verbose)

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
        raise click.ClickException("Installation check failed!")


# add subcommands
vedc.add_command(record)
vedc.add_command(update)
vedc.add_command(check_install)
