import inspect

import click
import pupil_recording_interface as pri
from blessed import Terminal
from confuse import ConfigTypeError, NotFoundError

from ved_capture.cli.utils import init_logger, raise_error
from ved_capture.config import ConfigParser


@click.command("estimate_cam_params")
@click.argument("streams", nargs=-1)
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
@click.option(
    "-e",
    "--extrinsics",
    default=False,
    help="Also estimate extrinsics between cameras.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def estimate_cam_params(streams, config_file, extrinsics, verbose):
    """ Estimate camera parameters. """

    # set up output
    t = Terminal()
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # parse config
    try:
        config_parser = ConfigParser(config_file)
        stream_configs = config_parser.get_cam_param_configs(
            *streams, extrinsics=extrinsics
        )
        folder = config_parser.get_folder("estimate_cam_params", None)
    except (ConfigTypeError, NotFoundError, KeyError) as e:
        raise_error(f"Error parsing configuration: {e.msg}", logger)

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy="here")

    # run manager
    with manager:
        while not manager.stopped:
            if manager.all_streams_running:
                response = input(
                    t.bold(
                        "Press enter to capture a pattern or type 's' to "
                        "stop: "
                    )
                )
                if response == "s":
                    break
                else:
                    manager.send_notification({"acquire_pattern": True})
                    manager.await_status(streams[0], pattern_acquired=True)

    # stop
    print(t.clear_eol + t.bold(t.firebrick("Stopped")))
