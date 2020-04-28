import inspect

import click
import pupil_recording_interface as pri
from blessed import Terminal
from confuse import ConfigTypeError, NotFoundError

from ved_capture.cli.utils import init_logger, raise_error
from ved_capture.config import ConfigParser


@click.command("calibrate")
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def calibrate(config_file, verbose):
    """ Calibrate gaze mapping. """

    # set up output
    t = Terminal()
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # parse config
    try:
        config_parser = ConfigParser(config_file)
        stream_configs = config_parser.get_calibration_configs()
        folder = config_parser.get_folder("calibrate", None)
    except (ConfigTypeError, NotFoundError, KeyError) as e:
        raise_error(f"Error parsing configuration: {e.msg}", logger)

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy="here")

    # run manager
    with manager:
        while not manager.stopped:
            if manager.all_streams_running:
                # Collect data
                response = input(
                    t.bold(
                        "Press enter to start calibration or type 'a' to "
                        "abort: "
                    )
                )
                if response == "a":
                    break
                else:
                    print("Collecting calibration data...")
                    manager.send_notification(
                        {"resume_process": "world.CircleDetector"},
                        streams=["world"],
                    )
                    manager.send_notification(
                        {"collect_calibration_data": True}, streams=["world"],
                    )
                    manager.await_status("world", collected_markers=None)

                # Calculate calibration
                response = input(
                    t.bold(
                        "Press enter to stop calibration or type 'a' to "
                        "abort: "
                    )
                )
                if response == "a":
                    break
                else:
                    manager.send_notification(
                        {"pause_process": "world.CircleDetector"},
                        streams=["world"],
                    )
                    manager.send_notification({"calculate_calibration": True})
                    manager.await_status("world", calibration_calculated=True)

    # stop
    print(t.clear_eol + t.bold(t.firebrick("Stopped")))
