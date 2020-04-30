""" ``vec_capture.cli`` bundles a variety of command line interfaces. """

import click

from ved_capture._version import __version__
from ved_capture.cli.app import update, check_install
from ved_capture.cli.calibrate import calibrate
from ved_capture.cli.cam_params import estimate_cam_params
from ved_capture.cli.config import generate_config
from ved_capture.cli.record import record


@click.group("vedc")
@click.version_option(version=__version__)
def vedc():
    """ Visual Experience Data Capture.

    Command line tool for the Visual Experience Database.
    """


# add subcommands
vedc.add_command(record)
vedc.add_command(calibrate)
vedc.add_command(estimate_cam_params)
vedc.add_command(generate_config)
vedc.add_command(update)
vedc.add_command(check_install)