import inspect

import click
import pupil_recording_interface as pri

from ved_capture import APP_INFO
from ved_capture.cli.ui import TerminalUI
from ved_capture.cli.utils import add_file_handler
from ved_capture.utils import copy_intrinsics, beep
from ved_capture.config import ConfigParser, save_metadata


def pause_recording(manager):
    """ Pause video recording. """
    beep([880, 660, 440])
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoRecorder"},
            streams=[stream],
        )


def resume_recording(manager):
    """ Resume video recording. """
    beep([440, 660, 880])
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoRecorder"},
            streams=[stream],
        )


def show_video_streams(manager):
    """ Show video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoDisplay"},
            streams=[stream],
        )


def hide_video_streams(manager):
    """ Hide video streams. """
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoDisplay"},
            streams=[stream],
        )


@click.command("record")
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the arguments ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml in the app config folder.'",
)
@click.option(
    "-v",
    "--verbose",
    default=False,
    help="Verbose output.",
    count=True,
)
def record(config_file, verbose):
    """ Run recording. """
    # TODO create temporary file handler that will be renamed once we have
    #  the recording folder
    ui = TerminalUI(
        inspect.stack()[0][3], verbosity=verbose, file_handler=False
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
        show_video = config_parser.get_show_video()

    # init manager
    manager = pri.StreamManager(
        stream_configs, folder=folder, policy=policy, app_info=APP_INFO
    )
    add_file_handler("record", manager.folder)
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    print(f"{ui.term.bold('Started recording')} to {manager.folder}")

    # write files to recording folder
    with open(manager.folder / "config.yaml", "w") as f:
        f.write(config_parser.config.dump(manager.folder / "config.yaml"))

    if len(metadata) > 0:
        save_metadata(manager.folder, metadata)
        ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

    for stream in manager.streams.values():
        copy_intrinsics(stream, intrinsics_folder, manager.folder)

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
