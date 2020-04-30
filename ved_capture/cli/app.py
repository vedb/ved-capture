import importlib
import inspect
import traceback

import click
from git import GitError

from ved_capture.cli.utils import init_logger, raise_error
from ved_capture.utils import get_paths, update_repo, update_environment


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

    for module in ["uvc", "pupil_detectors", "PySpin", "pyrealsense2"]:
        check_import(module)

    if len(failures) == 0:
        logger.info("Installation check OK.")
    else:
        raise_error("Installation check failed!", logger)