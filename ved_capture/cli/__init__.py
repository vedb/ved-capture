""" ``vec_capture.cli`` bundles a variety of command line interfaces. """

import click

from ved_capture.cli.app import update, check_install, save_logs
from ved_capture.cli.calibrate import calibrate
from ved_capture.cli.validate import validate
from ved_capture.cli.cam_params import estimate_cam_params
from ved_capture.cli.config import generate_config, auto_config, edit_config
from ved_capture.cli.record import record
from ved_capture.cli.show import show
from ved_capture.cli.export import export
from ved_capture.cli.device_info import device_info


@click.group("vedc")
@click.version_option()
def vedc():
    """ Visual Experience Data Capture.

    Command line tool for the Visual Experience Database.

    \b
    For more information check out the wiki:
    https://github.com/vedb/ved-capture/wiki
    """


# add subcommands
vedc.add_command(record)
vedc.add_command(calibrate)
vedc.add_command(validate)
vedc.add_command(estimate_cam_params)
vedc.add_command(show)
vedc.add_command(generate_config)
vedc.add_command(auto_config)
vedc.add_command(edit_config)
vedc.add_command(check_install)
vedc.add_command(save_logs)
vedc.add_command(export)
vedc.add_command(device_info)
