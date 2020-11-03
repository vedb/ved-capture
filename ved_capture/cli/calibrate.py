import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.commands import (
    collect_calibration_data,
    calculate_calibration,
    show_video_streams,
    hide_video_streams,
)
from ved_capture.cli.ui import TerminalUI
from ved_capture.config import ConfigParser


@click.command("calibrate")
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the argument ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml in the app config folder.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def calibrate(config_file, verbose):
    """ Calibrate gaze mapping. """
    ui = TerminalUI(inspect.stack()[0][3], verbosity=verbose)

    # parse config
    with ConfigParser(config_file) as config_parser:
        stream_configs = config_parser.get_calibration_configs()
        folder = config_parser.get_folder("calibrate", None)
        # TODO make this more robust
        world_stream = stream_configs[0].name

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
    ui.add_key(
        "c",
        "collect calibration data",
        lambda x: collect_calibration_data(x, world_stream),
        msg="Collecting calibration data",
        alt_description="calculate calibration",
        alt_fn=lambda x: calculate_calibration(x, world_stream),
        alt_msg="Calculating calibration",
    )

    # spin
    with ui, manager:
        ui.spin()
