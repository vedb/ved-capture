import inspect

import click
import pupil_recording_interface as pri

from ved_capture.cli.ui import TerminalUI
from ved_capture.config import ConfigParser, save_metadata


def show_video_streams(ui, manager, key):
    """ Show video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoDisplay"}, streams=[stream],
        )

    ui.logger.info("Showing video streams")
    ui.keymap[key] = (
        "hide video streams",
        lambda: hide_video_streams(ui, manager, key),
    )


def hide_video_streams(ui, manager, key):
    """ Hide video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoDisplay"}, streams=[stream],
        )

    ui.logger.info("Hiding video streams")
    ui.keymap[key] = (
        "show video streams",
        lambda: show_video_streams(ui, manager, key),
    )


def pause_recording(ui, manager, key):
    """ Pause video recording. """
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )

    ui.logger.info("Pausing recording")
    ui.keymap[key] = (
        "resume recording",
        lambda: resume_recording(ui, manager, key),
    )


def resume_recording(ui, manager, key):
    """ Resume video recording. """
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )

    ui.logger.info("Resuming recording")
    ui.keymap[key] = (
        "pause recording",
        lambda: pause_recording(ui, manager, key),
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

    keymap = {
        "r": ("pause recording", lambda: pause_recording(ui, manager, "r")),
    }
    if show_video:
        keymap["v"] = (
            "hide video streams",
            lambda: hide_video_streams(ui, manager, "v"),
        )
    else:
        keymap["v"] = (
            "show video streams",
            lambda: show_video_streams(ui, manager, "v"),
        )

    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"}, keymap=keymap)

    # spin
    with ui, manager:
        print(f"{ui.term.bold('Started recording')} to {manager.folder}")
        if len(metadata) > 0:
            save_metadata(manager.folder, metadata)
            ui.logger.debug(f"Saved user_info.csv to {manager.folder}")
        ui.spin()
