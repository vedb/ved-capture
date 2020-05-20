""""""
import os
import json
import logging
import shutil
import subprocess
from select import select

import git
import pupil_recording_interface as pri
from pupil_recording_interface.externals.file_methods import load_object

logger = logging.getLogger(__name__)


def log_as_warning_or_debug(data):
    """ Log message as warning, unless it's known to be a debug message. """
    _suppress_if_startswith = (
        b"[sudo] ",
        b'Please run using "bash" or "sh"',
        b"==> WARNING: A newer version of conda exists. <==",
    )

    _suppress_if_endswith = (b"is not a symbolic link",)

    _suppress_if_contains = (b"Extracting : ",)

    data = data.strip(b"\n")

    if (
        data.startswith(_suppress_if_startswith)
        or data.endswith(_suppress_if_endswith)
        or any(data.find(s) for s in _suppress_if_contains)
    ):
        logger.debug(data.decode("utf-8"))
    else:
        logger.warning(data.decode("utf-8"))


def log_as_debug(data):
    """ Log message as debug. """
    logger.debug(data.rstrip(b"\n").decode("utf-8"))


def run_command(command, shell=False, n_bytes=4096):
    """ Run system command and pipe output to logger. """
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell,
    ) as process:
        readable = {
            process.stdout.fileno(): log_as_debug,
            process.stderr.fileno(): log_as_warning_or_debug,
        }
        while readable:
            for fd in select(readable, [], [])[0]:
                data = os.read(fd, n_bytes)  # read available
                if not data:  # EOF
                    del readable[fd]
                else:
                    readable[fd](data)

        return process.wait()


def get_paths(config_folder="~/.config/vedc"):
    """ Get dictionary with application paths. """
    try:
        with open(
            os.path.join(os.path.expanduser(config_folder), "paths.json")
        ) as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return None


def update_repo(repo_folder, stash=False):
    """ Update repository. """
    repo = git.Repo(repo_folder)
    current_hash = repo.head.object.hexsha

    if stash:
        repo.git.stash()
    repo.remotes.origin.pull()
    pull_hash = repo.head.object.hexsha

    return current_hash != pull_hash


def update_environment(
    conda_binary,
    conda_script,
    repo_folder,
    env_file="environment.yml",
    local=False,
):
    """ Update conda environment. """
    return_code = run_command(
        [
            conda_binary,
            "env",
            "update",
            "-f",
            os.path.join(repo_folder, env_file),
        ]
    )

    if local:
        run_command(
            f"/bin/bash -c '. {conda_script} && conda activate vedc "
            f"&& pip install --no-deps -U -e {repo_folder}'",
            shell=True,
        )

    return return_code


def get_pupil_devices():
    """ Get names and UIDs of connected Pupil cameras. """
    connected_devices = pri.VideoDeviceUVC._get_connected_device_uids()
    pupil_cams = {
        name: uid
        for name, uid in connected_devices.items()
        if name.startswith("Pupil Cam")
    }
    return pupil_cams


def get_realsense_devices():
    """ Get serial numbers of connected RealSense devices. """
    return pri.RealSenseDeviceT265.get_serial_numbers()


def get_flir_devices():
    """ Get serial numbers connected FLIR cameras. """
    import PySpin

    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    logger.debug(f"Number of cameras detected: {cam_list.GetSize()}")

    serials = []
    for camera in cam_list:
        nodemap = camera.GetTLDeviceNodeMap()
        serial_number_node = PySpin.CStringPtr(
            nodemap.GetNode("DeviceSerialNumber")
        )
        if PySpin.IsAvailable(serial_number_node) and PySpin.IsReadable(
            serial_number_node
        ):
            serials.append(serial_number_node.GetValue())
        else:
            logger.warning(f"Could not get serial number for camera {camera}")
        del camera

    cam_list.Clear()

    return serials


def copy_intrinsics(stream, src_folder, dst_folder):
    """ Copy intrinsics for a stream. """
    if isinstance(stream, pri.VideoStream):
        src_file = os.path.join(
            src_folder,
            f"{stream.device.device_uid.replace(' ', '_')}.intrinsics",
        )
        if not os.path.exists(src_file):
            logger.warning(
                f"No intrinsics for device '{stream.device.device_uid}' "
                f"found in {src_folder}"
            )
        else:
            intrinsics = load_object(src_file)
            resolution = tuple(stream.device.resolution)
            if str(resolution) not in intrinsics:
                logger.warning(
                    f"Intrinsics for device '{stream.device.device_uid}' "
                    f"at resolution {resolution} not found in "
                    f"{src_file}"
                )
            else:
                dst_file = os.path.join(
                    dst_folder, f"{stream.name}.intrinsics"
                )
                shutil.copyfile(src_file, dst_file)
                logger.debug(f"Copied {src_file} to {dst_file}")
