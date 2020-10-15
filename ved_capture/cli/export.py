from pathlib import Path
import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.utils import init_logger, raise_error


@click.command("export")
@click.argument("folder")
@click.argument("topics", nargs=-1)
@click.option("-f", "--format", default="netcdf", help="Export format.")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def export(folder, topics, format, verbose):
    """ Export recording data. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # TODO pupil
    supported_topics = ("gaze", "odometry", "accel", "gyro")

    folder = Path(folder)

    if not folder.exists():
        raise_error(f"{folder} does not exist", logger)

    if len(topics) == 0:
        topics = [
            topic.stem
            for topic in folder.iterdir()
            if topic.suffix == ".pldata" and topic.stem in supported_topics
        ]

    if len(topics) == 0:
        raise_error(f"{folder} does not contain any exportable data", logger)
    else:
        for topic in topics:
            if topic not in supported_topics:
                raise_error(
                    f"'{topic}' is not one of the supported topics "
                    f"{supported_topics}"
                )

    if format.lower() in ("netcdf", "nc"):
        try:
            # TODO support offline data
            pri.write_netcdf(
                folder, **{topic: "recording" for topic in topics}
            )
        except FileNotFoundError as e:
            raise_error(str(e), logger)
    else:
        raise_error(f"Unsupported format: {format}", logger)
