import inspect
import simpleaudio
import click
import pupil_recording_interface as pri

from ved_capture import APP_INFO
from ved_capture.cli.ui import TerminalUI
from ved_capture.utils import copy_intrinsics
from ved_capture.config import ConfigParser, save_metadata


def pause_recording(manager):
    """ Pause video recording. """
    beep([880, 660, 440])
    for stream in manager.streams:
        manager.send_notification(
            {"pause_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def resume_recording(manager):
    """ Resume video recording. """
    beep([440, 660, 880])
    for stream in manager.streams:
        manager.send_notification(
            {"resume_process": f"{stream}.VideoRecorder"}, streams=[stream],
        )


def beep(freq=440, fs=44100, seconds=0.1): 
    """Make a beep noise to indicate recording state"""
    import numpy as np
    t = np.linspace(0, seconds, fs*seconds) 
    if not isinstance(freq, list): 
        freq = [freq] 
    notes = np.hstack([np.sin(f*t*2*np.pi) for f in freq]) 
    audio = (notes * (2**15 -1) / np.max(np.abs(notes))).astype(np.int16) 
    play_obj = simpleaudio.play_buffer(audio, 1, 2, fs)
           

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
    "-c", "--config-file", default=None, help="Path to config file.",
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
        intrinsics_folder = config_parser.get_folder(
            "estimate_cam_params", None, **metadata
        )
        policy = config_parser.get_policy("record")
        show_video = config_parser.get_show_video()

    # init manager
    manager = pri.StreamManager(
        stream_configs, folder=folder, policy=policy, app_info=APP_INFO
    )
    ui.attach(manager, statusmap={"fps": "{:.2f} Hz"})

    print(f"{ui.term.bold('Started recording')} to {manager.folder}")
    if len(metadata) > 0:
        save_metadata(manager.folder, metadata)
        ui.logger.debug(f"Saved user_info.csv to {manager.folder}")

    for stream in manager.streams.values():
        copy_intrinsics(stream, intrinsics_folder, folder)

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
    ui.add_key(
        "KEY_PGUP",
        "pause recording",
        pause_recording,
        msg="Pausing video recording",
        #alt_key="r",
        alt_description="resume recording",
        alt_fn=resume_recording,
        alt_msg="Resuming video recording",
    )

    # spin
    with ui, manager:
        ui.spin()
