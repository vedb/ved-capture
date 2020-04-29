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


@click.command("calibrate")
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
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

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy="here")
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    # add keyboard commands
    ui.add_key(
        "c",
        "collect calibration data",
        collect_calibration_data,
        msg="Collecting calibration data",
        alt_description="calculate calibration",
        alt_fn=calculate_calibration,
        alt_msg="Calculating calibration",
    )

    # spin
    with ui, manager:
        ui.spin()
