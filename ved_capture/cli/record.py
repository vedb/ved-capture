import inspect
import io

import click
import pupil_recording_interface as pri
from blessed import Terminal
from confuse import ConfigTypeError, NotFoundError

from ved_capture.cli.utils import init_logger, raise_error, print_log_buffer
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

    # set up output
    t = Terminal()
    f_stdout = io.StringIO()
    logger = init_logger(
        inspect.stack()[0][3],
        verbosity=verbose,
        stream=f_stdout,
        stream_format="[%(levelname)s] %(message)s",
    )

    # parse config
    try:
        config_parser = ConfigParser(config_file)
        metadata = config_parser.get_metadata()
        stream_configs = config_parser.get_recording_configs()
        folder = config_parser.get_folder("record", None, **metadata)
        policy = config_parser.get_policy("record")
    except (ConfigTypeError, NotFoundError, KeyError) as e:
        raise_error(f"Error parsing configuration: {e.msg}", logger)

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy=policy)

    # run manager
    with manager:
        print(
            t.bold(t.turquoise3("Started recording")) + f" to {manager.folder}"
        )
        if len(metadata) > 0:
            save_metadata(manager.folder, metadata)
            logger.debug(f"Saved user_info.csv to {manager.folder}")

        while not manager.stopped:
            print_log_buffer(f_stdout)
            if manager.all_streams_running:
                status_str = manager.format_status("fps", max_cols=t.width)
                with t.hidden_cursor():
                    with t.location(0, t.height - 1):
                        print(
                            t.clear_eol
                            + t.bold(t.turquoise3(status_str))
                            + t.move_up
                        )
            else:
                with t.hidden_cursor():
                    with t.location(0, t.height - 1):
                        print(
                            t.clear_eol
                            + t.bold(t.turquoise3("Waiting for init"))
                            + t.move_up
                        )

    # stop
    print(t.clear_eol)
    print_log_buffer(f_stdout)
    with t.location(0, t.height - 1):
        print(t.clear_eol + t.bold(t.firebrick("Stopped recording")))
