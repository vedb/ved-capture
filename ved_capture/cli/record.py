import inspect

import click
import pupil_recording_interface as pri
from confuse import ConfigTypeError, NotFoundError

from ved_capture.cli.ui import TerminalUI
from ved_capture.cli.utils import raise_error
from ved_capture.config import ConfigParser, save_metadata


@click.command("record")
@click.option(
    "-c", "--config-file", default=None, help="Path to recording config file.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def record(config_file, verbose):
    """ Run recording. """
    ui = TerminalUI(inspect.stack()[0][3], verbosity=verbose)

    # parse config
    try:
        config_parser = ConfigParser(config_file)
        metadata = config_parser.get_metadata()
        stream_configs = config_parser.get_recording_configs()
        folder = config_parser.get_folder("record", None, **metadata)
        policy = config_parser.get_policy("record")
    except (ConfigTypeError, NotFoundError, KeyError) as e:
        raise_error(f"Error parsing configuration: {e}", ui.logger)

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy=policy)
    ui.attach(
        manager,
        statusmap={"fps": "{:.2f} Hz"},
        keymap={"ctrl+c": ("quit", ui.nop)},
    )

    # run manager
    with manager:
        print(f"{ui.term.bold('Started recording')} to {manager.folder}")

        if len(metadata) > 0:
            save_metadata(manager.folder, metadata)
            ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

        ui.spin()
