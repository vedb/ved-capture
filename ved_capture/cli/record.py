import inspect

import click
import pupil_recording_interface as pri

from ved_capture import APP_INFO
from ved_capture.cli.commands import (
    pause_recording,
    resume_recording,
    show_video_streams,
    hide_video_streams,
)
from ved_capture.cli.ui import TerminalUI
from ved_capture.utils import (
    copy_cam_params,
    check_disk_space,
    set_profile_from_metadata,
)
from ved_capture.config import ConfigParser, save_metadata


@click.command("record")
@click.option(
    "-c",
    "--config-file",
    default=None,
    help="Path or name of config file. If the argument ends with '.yaml', it "
    "is assumed to be a path. Otherwise, it will look for a file called "
    "'<CONFIG_FILE>.yaml' in the app config folder.",
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
        set_profile_from_metadata(config_parser, metadata)
        stream_configs = config_parser.get_recording_configs()
        folder = config_parser.get_folder("record", None, **metadata)
        cam_params_folder = config_parser.get_folder(
            "estimate_cam_params", None, **metadata
        )
        policy = config_parser.get_policy("record")
        duration = config_parser.get_duration("record")
        intrinsics, extrinsics = config_parser.get_recording_cam_params()

    # init manager
    manager = pri.StreamManager(
        stream_configs,
        folder=folder,
        policy=policy,
        duration=duration,
        app_info=APP_INFO,
    )
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    print(f"{ui.term.bold('Started recording')} to {manager.folder}")

    # check free disk space
    check_disk_space(folder)

    # write files to recording folder
    with open(manager.folder / "config.yaml", "w") as f:
        f.write(config_parser.config.dump(manager.folder / "config.yaml"))
        ui.logger.debug(f"Saved config.yaml to {manager.folder}")

    if len(metadata) > 0:
        save_metadata(manager.folder, metadata)
        ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

    copy_cam_params(
        manager.streams,
        cam_params_folder,
        manager.folder,
        intrinsics,
        extrinsics,
    )

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
