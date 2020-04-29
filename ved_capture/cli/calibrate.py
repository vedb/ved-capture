import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.ui import TerminalUI
from ved_capture.config import ConfigParser


def collect_calibration_data(ui, manager, key):
    """ Start data collection. """
    manager.send_notification(
        {"resume_process": "world.CircleDetector"}, streams=["world"],
    )
    manager.send_notification(
        {"collect_calibration_data": True}, streams=["world"],
    )

    ui.logger.info("Collecting calibration data")
    ui.keymap[key] = (
        "calculate calibration",
        lambda: calculate_calibration(ui, manager, key),
    )


def calculate_calibration(ui, manager, key):
    """ Stop data collection and run calibration. """
    ui.logger.info("Calculating calibration")

    manager.send_notification(
        {"pause_process": "world.CircleDetector"}, streams=["world"],
    )
    manager.send_notification({"calculate_calibration": True})

    ui.keymap[key] = (
        "collect calibration data",
        lambda: collect_calibration_data(ui, manager, key),
    )


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
    ui.attach(
        manager,
        statusmap={"fps": "{:.2f} Hz"},
        keymap={
            "c": (
                "collect calibration data",
                lambda: collect_calibration_data(ui, manager, "c"),
            ),
        },
    )

    # spin
    with ui, manager:
        ui.spin()
