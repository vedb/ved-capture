""" ``vec_capture.cli`` bundles a variety of command line interfaces. """

import logging
import inspect
import importlib
import traceback

import click

from pupil_recording_interface import MultiStreamRecorder

from ved_capture.config import ConfigParser, save_metadata


def _init_logger(subcommand, verbose=False):
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

    return logger


@click.group("vedc")
def vedc():
    """ vedc command line interface. """


@click.command("record")
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
def record(config_file):
    """ Run recording. """
    config_parser = ConfigParser(config_file)

    metadata = config_parser.get_metadata()

    recorder = MultiStreamRecorder(
        config_parser.get_recording_folder(None, **metadata),
        config_parser.get_recording_configs(),
        show_video=True,
    )

    save_metadata(recorder.folder, metadata)
    recorder.run()


@click.command("check_install")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", is_flag=True,
)
def check_install(verbose):
    """ Test installation. """
    logger = _init_logger(str(inspect.currentframe()), verbose=verbose)

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
vedc.add_command(check_install)
