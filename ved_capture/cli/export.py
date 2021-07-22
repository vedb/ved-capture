import inspect
import json
from pathlib import Path
from pprint import pformat

import click
import pupil_recording_interface as pri

from ved_capture.cli.utils import init_logger, raise_error


@click.command("export")
@click.argument("file-type")
@click.argument("folder")
@click.argument("topics", nargs=-1)
@click.option(
    "-f", "--format", default="auto", help="Export format.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def export(folder, topics, file_type, format, verbose):
    """ Export recording data.

    This tool will export all topics that match 'file-type', e.g.,
    'vedc export intrinsics' will export all '.intrinsics' files. You can also
    specify the topics that you want to export at the end.

    Available file types are 'intrinsics', 'extrinsics' and 'pldata'.

    \b
    Note that supported formats depend on file type:
    - auto: auto-determine format for file type.
    - json: json format. Not supported for pldata types.
    - nc, netcdf: netCDF4 format. Supported for pldata types.
    - echo: print export to command line. Not supported for pldata types.
    """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # check folder
    folder = Path(folder)
    if not folder.exists():
        raise_error(f"{folder} does not exist", logger)

    # set supported formats and topics based on file type
    if file_type == "pldata":
        supported_formats = ("netcdf", "nc")
        supported_topics = ("gaze", "odometry", "accel", "gyro")  # TODO pupil
    else:
        supported_formats = ("json", "echo")
        supported_topics = None

    # auto-determine format or check if format is supported for file type
    if format == "auto":
        format = supported_formats[0]
    elif format not in supported_formats:
        raise_error(
            f"{file_type} file type can't be exported as {format}, "
            f"supported formats are {supported_formats}",
            logger,
        )

    # auto-discover exportable topics if not specified by user
    topics = list(topics)
    if len(topics) == 0:
        for filename in folder.iterdir():
            if filename.suffix == f".{file_type}" and (
                supported_topics is None or filename.stem in supported_topics
            ):
                topics.append(filename.stem)

    # check if any exportable topics are specified
    if len(topics) == 0:
        raise_error(f"{folder} does not contain any exportable data", logger)

    # check if all specified topics are exportable
    if supported_topics is not None:
        for topic in topics:
            if topic not in supported_topics:
                raise_error(
                    f"'{topic}' is not one of the supported topics "
                    f"{supported_topics}"
                )

    # run export according to format
    if format.lower() in ("netcdf", "nc"):
        try:
            # TODO support offline data
            pri.write_netcdf(
                folder, **{topic: "recording" for topic in topics}
            )
        except FileNotFoundError as e:
            raise_error(str(e), logger)

    elif format.lower() == "json":
        export_folder = folder / "exports"
        export_folder.mkdir(exist_ok=True)
        try:
            for topic in topics:
                obj = pri.load_object(folder / f"{topic}.{file_type}")
                with open(
                    export_folder / f"{topic}.{file_type}.json", "w"
                ) as f:
                    f.write(json.dumps(obj, indent=4))
        except FileNotFoundError as e:
            raise_error(str(e), logger)

    elif format.lower() == "echo":
        try:
            for topic in topics:
                obj = pri.load_object(folder / f"{topic}.{file_type}")
                filename = f"{topic}.{file_type}"
                header = f"{filename}\n{'-'*len(filename)}\n"
                logger.info(f"{header}{pformat(obj)}\n")
        except FileNotFoundError as e:
            raise_error(str(e), logger)

    else:
        raise_error(f"Unsupported format: {format}", logger)
