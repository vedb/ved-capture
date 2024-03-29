import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.ui import TerminalUI
from ved_capture.cli.utils import raise_error
from ved_capture.config import ConfigParser


@click.command("show")
@click.argument("streams", nargs=-1)
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the argument ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml' in the app config folder.",
)
@click.option(
    "-p",
    "--profile",
    default=None,
    help="Stream profile to apply. Must be defined in default config or user"
    "config.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def show(streams, config_file, profile, verbose):
    """ Show video streams. """
    ui = TerminalUI(inspect.stack()[0][3], verbosity=verbose)

    if len(streams) == 0:
        raise_error("Please specify at least one stream to show")

    # parse config
    with ConfigParser(config_file) as config_parser:
        if profile is not None:
            config_parser.set_profile(profile)
        stream_configs = config_parser.get_show_configs(*streams)

    # init manager
    manager = pri.StreamManager(stream_configs)
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    # spin
    with ui, manager:
        ui.spin()
