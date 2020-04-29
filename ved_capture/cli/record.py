import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.ui import TerminalUI
from ved_capture.config import ConfigParser, save_metadata


def pause_recording(manager):
    """ Pause video recording. """
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def resume_recording(manager):
    """ Resume video recording. """
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def show_video_streams(manager):
    """ Show video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoDisplay"}, streams=[stream],
        )


def hide_video_streams(manager):
    """ Hide video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoDisplay"}, streams=[stream],
        )


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
    with ConfigParser(config_file) as config_parser:
        metadata = config_parser.get_metadata()
        stream_configs = config_parser.get_recording_configs()
        folder = config_parser.get_folder("record", None, **metadata)
        policy = config_parser.get_policy("record")
        show_video = config_parser.get_show_video()

    # init manager
    manager = pri.StreamManager(stream_configs, folder=folder, policy=policy)
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    print(f"{ui.term.bold('Started recording')} to {manager.folder}")
    if len(metadata) > 0:
        save_metadata(manager.folder, metadata)
        ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

    # set keyboard commands
    ui.add_key(
        "s",
        "show video streams",
        show_video_streams,
        msg="Showing video streams",
        alt_key="h",
        alt_description="hide video streams",
        alt_fn=hide_video_streams,
        alt_msg="Hiding video streams",
        alt_default=show_video,
    )
    ui.add_key(
        "p",
        "pause recording",
        pause_recording,
        msg="Pausing video recording",
        alt_key="r",
        alt_description="resume recording",
        alt_fn=resume_recording,
        alt_msg="Resuming video recording",
    )

    # spin
    with ui, manager:
        ui.spin()
