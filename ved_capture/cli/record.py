import inspect
from functools import partial

import click
import pupil_recording_interface as pri

from ved_capture import APP_INFO
from ved_capture.cli.ui import TerminalUI
from ved_capture.utils import copy_intrinsics, beep
from ved_capture.config import ConfigParser, save_metadata


def pause_recording(ui):
    """ Pause video recording. """
    beep([880, 660, 440])
    for stream in ui.manager.streams:
        ui.manager.send_notification(
            {"pause_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def resume_recording(ui):
    """ Resume video recording. """
    beep([440, 660, 880])
    for stream in ui.manager.streams:
        ui.manager.send_notification(
            {"resume_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def show_video_streams(ui):
    """ Show video streams. """
    old_keymap = ui.keymap
    new_keymap = {}

    video_streams = tuple(
        stream
        for stream in ui.manager.streams
        if isinstance(ui.manager.streams[stream], pri.VideoStream)
    )

    def back():
        ui.fixed_status = None
        ui.keymap = old_keymap

    def show_one(stream):
        ui.logger.info(f"Showing video stream '{stream}'")
        ui.manager.send_notification(
            {"resume_process": f"{stream}.VideoDisplay"}, streams=[stream],
        )
        back()

    def show_all():
        ui.logger.info(f"Showing all video streams")
        for stream in list(video_streams):
            ui.manager.send_notification(
                {"resume_process": f"{stream}.VideoDisplay"}, streams=[stream],
            )
        back()

    for idx, stream in enumerate(video_streams):
        new_keymap[str(idx)] = (stream, partial(show_one, video_streams[idx]))

    new_keymap["a"] = ("all", show_all)
    new_keymap["b"] = ("back", back)

    ui.fixed_status = "Select a video stream to show:"
    ui.keymap = new_keymap


def hide_video_streams(ui):
    """ Hide video streams. """
    for stream in ui.manager.streams:
        if isinstance(ui.manager.streams[stream], pri.VideoStream):
            ui.manager.send_notification(
                {"pause_process": f"{stream}.VideoDisplay"}, streams=[stream],
            )


@click.command("record")
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the argument ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml in the app config folder.",
)
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def record(config_file, verbose):
    """ Run recording. """
    ui = TerminalUI(
        inspect.stack()[0][3], verbosity=verbose, temp_file_handler=True
    )

    # parse config
    with ConfigParser(config_file) as config_parser:
        metadata = config_parser.get_metadata()
        stream_configs = config_parser.get_recording_configs()
        folder = config_parser.get_folder("record", None, **metadata)
        intrinsics_folder = config_parser.get_folder(
            "estimate_cam_params", None, **metadata
        )
        policy = config_parser.get_policy("record")

    # init manager
    manager = pri.StreamManager(
        stream_configs, folder=folder, policy=policy, app_info=APP_INFO
    )
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    print(f"{ui.term.bold('Started recording')} to {manager.folder}")

    # write files to recording folder
    with open(manager.folder / "config.yaml", "w") as f:
        f.write(config_parser.config.dump(manager.folder / "config.yaml"))
        ui.logger.debug(f"Saved config.yaml to {manager.folder}")

    if len(metadata) > 0:
        save_metadata(manager.folder, metadata)
        ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

    for stream in manager.streams.values():
        copy_intrinsics(stream, intrinsics_folder, manager.folder)

    # set keyboard commands
    ui.add_key("s", "show streams", show_video_streams)
    ui.add_key(
        "h",
        "hide all streams",
        hide_video_streams,
        msg="Hiding all video streams",
    )
    ui.add_key(
        "KEY_PGUP",
        "pause recording",
        pause_recording,
        msg="Pausing video recording",
        alt_description="resume recording",
        alt_fn=resume_recording,
        alt_msg="Resuming video recording",
    )

    # spin
    with ui, manager:
        ui.spin()
