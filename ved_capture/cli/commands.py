from functools import partial

import pupil_recording_interface as pri

from ved_capture.utils import beep


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


def collect_calibration_data(ui, stream="world"):
    """ Start data collection. """
    ui.manager.send_notification(
        {"resume_process": f"{stream}.CircleDetector"}, streams=[stream],
    )
    ui.manager.send_notification(
        {"collect_calibration_data": True}, streams=[stream],
    )


def calculate_calibration(ui, stream="world"):
    """ Stop data collection and run calibration. """
    ui.manager.send_notification(
        {"pause_process": f"{stream}.CircleDetector"}, streams=[stream],
    )
    ui.manager.send_notification({"calculate_calibration": True})


def acquire_pattern(ui):
    """ Acquire a new calibration pattern. """
    ui.manager.send_notification({"acquire_pattern": True})
