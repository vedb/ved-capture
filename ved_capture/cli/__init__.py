""" ``vec_capture.cli`` bundles a variety of command line interfaces. """

import click

from ved_capture._version import __version__
from ved_capture.cli.app import update, check_install, save_logs
from ved_capture.cli.calibrate import calibrate
from ved_capture.cli.cam_params import estimate_cam_params
from ved_capture.cli.config import generate_config, edit_config
from ved_capture.cli.record import record
from ved_capture.cli.show import show
from ved_capture.cli.export import export


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
vedc.add_command(show)
vedc.add_command(generate_config)
vedc.add_command(edit_config)
vedc.add_command(update)
vedc.add_command(check_install)
vedc.add_command(save_logs)
vedc.add_command(export)
