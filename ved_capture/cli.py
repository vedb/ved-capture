""" ``vec_capture.cli`` bundles a variety of command line interfaces. """

import logging
import inspect

import click


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


@click.group('vedc')
def vedc():
    """ vedc command line interface. """


@click.command('check_install')
def check_install():
    """ Test installation. """
    logger = _init_logger(str(inspect.currentframe()))

    try:
        import uvc
    except ImportError:
        logger.error("Could not import pyuvc.")
        raise click.ClickException("Self-test failed!")

    try:
        import PySpin
    except ImportError:
        logger.error("Could not import PySpin.")
        raise click.ClickException("Self-test failed!")


# add subcommands
vedc.add_command(check_install)
