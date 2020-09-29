import os
import importlib
import inspect
import traceback
import tarfile

import click
from git import GitError

from ved_capture.cli.utils import init_logger, raise_error
from ved_capture.utils import get_paths, update_repo, update_environment
from ved_capture.config import ConfigParser


@click.command("update")
@click.option(
    "-v",
    "--verbose",
    default=False,
    help="Verbose output.",
    count=True,
)
@click.option(
    "-l",
    "--local",
    default=False,
    help="Update from local repository.",
    is_flag=True,
)
@click.option(
    "-b",
    "--branch",
    default=None,
    help="Update from this branch or tag.",
)
@click.option(
    "-s",
    "--stash",
    default=False,
    help="Stash local changes.",
    count=True,
)
@click.option(
    "--pri_path",
    default=None,
    help="Path to local pupil_recording_interface repository.",
)
def update(verbose, local, branch, stash, pri_path):
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
            update_repo(paths["vedc_repo_folder"], branch, stash)
        except GitError as e:
            raise_error(f"Repository update failed. Reason: {str(e)}", logger)

    # update environment
    logger.info("Updating environment.\nThis will take a couple of minutes. ☕")
    return_code = update_environment(paths, local=local, pri_path=pri_path)
    if return_code != 0:
        raise_error(
            f"Environment update failed, please try running: python3 "
            f"{paths['vedc_repo_folder']}/installer/install_ved_capture.py",
            logger,
        )


@click.command("check_install")
@click.option(
    "-v",
    "--verbose",
    default=False,
    help="Verbose output.",
    count=True,
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

    for module in ["uvc", "pupil_detectors", "PySpin", "pyrealsense2"]:
        check_import(module)

    if len(failures) == 0:
        logger.info("Installation check OK.")
    else:
        raise_error("Installation check failed!", logger)


@click.command("save_logs")
@click.option(
    "-f",
    "--filepath",
    default="~/vedc_logs.tar.gz",
    help="Output file path.",
)
@click.option(
    "-o",
    "--overwrite",
    default=False,
    help="Overwrite existing file.",
    is_flag=True,
)
def save_logs(filepath, overwrite):
    """ Save logs to a gzipped tar archive. """
    filepath = os.path.expanduser(filepath)
    source_dir = ConfigParser.config_dir()

    if os.path.exists(filepath) and not overwrite:
        raise click.ClickException(
            f"{filepath} exists, set -o/--overwrite flag to overwrite"
        )

    with tarfile.open(filepath, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
