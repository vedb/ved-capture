import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.commands import (
    acquire_pattern,
    show_video_streams,
    hide_video_streams,
)
from ved_capture.cli.ui import TerminalUI
from ved_capture.cli.utils import raise_error
from ved_capture.config import ConfigParser


@click.command("estimate_cam_params")
@click.argument("streams", nargs=-1)
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the argument ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml in the app config folder.",
)
@click.option(
    "-e",
    "--extrinsics",
    default=False,
    help="Also estimate extrinsics between cameras.",
    is_flag=True,
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def estimate_cam_params(streams, config_file, extrinsics, verbose):
    """ Estimate camera parameters. """
    ui = TerminalUI(inspect.stack()[0][3], verbosity=verbose)

    if len(streams) == 0:
        raise_error(
            "Please specify at least one stream for parameter estimation"
        )

    # parse config
    with ConfigParser(config_file) as config_parser:
        stream_configs = config_parser.get_cam_param_configs(
            *streams, extrinsics=extrinsics
        )
        folder = config_parser.get_folder("estimate_cam_params", None)

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy="here")
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    # add keyboard commands
    ui.add_key("s", "show streams", show_video_streams)
    ui.add_key(
        "h",
        "hide all streams",
        hide_video_streams,
        msg="Hiding all video streams",
    )
    ui.add_key("i", "acquire pattern", acquire_pattern)

    # spin
    with ui, manager:
        ui.spin()
