import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.ui import TerminalUI
from ved_capture.config import ConfigParser


def collect_calibration_data(manager, stream="world"):
    """ Start data collection. """
    manager.send_notification(
        {"resume_process": f"{stream}.CircleDetector"}, streams=[stream],
    )
    manager.send_notification(
        {"collect_calibration_data": True}, streams=[stream],
    )


def calculate_calibration(manager, stream="world"):
    """ Stop data collection and run calibration. """
    manager.send_notification(
        {"pause_process": f"{stream}.CircleDetector"}, streams=[stream],
    )
    manager.send_notification({"calculate_calibration": True})


@click.command("validate")
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the arguments ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml in the app config folder.'",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def validate(config_file, verbose):
    """ Calibrate gaze mapping. """
    ui = TerminalUI(inspect.stack()[0][3], verbosity=verbose)

    # parse config
    with ConfigParser(config_file) as config_parser:
        stream_configs = config_parser.get_validation_configs()
        folder = config_parser.get_folder("record", None)
        # TODO make this more robust
        world_stream = stream_configs[0].name

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy="here")
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    # add keyboard commands
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
