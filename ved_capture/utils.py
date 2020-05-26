""""""
import os
import json
import logging
import shutil
import subprocess
from pathlib import Path
from select import select
from pkg_resources import parse_version

import git
import pupil_recording_interface as pri
from pupil_recording_interface.externals.file_methods import load_object

from ved_capture.config import ConfigParser

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


def get_paths():
    """ Get dictionary with application paths. """
    try:
        with open(Path(ConfigParser.config_dir()) / "paths.json") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return None


def update_repo(repo_folder, branch=None, stash=False):
    """ Update repository. """
    repo = git.Repo(repo_folder)
    current_hash = repo.head.object.hexsha

    # fetch updates
    repo.remotes.origin.fetch()
    if stash:
        repo.git.stash()

    # get latest version or specified branch
    branch = (
        branch or sorted(repo.tags, key=lambda t: parse_version(t.name))[-1]
    )
    repo.git.checkout(branch)
    logger.info(f"Checked out {branch}")

    # Return True if the repo was updated
    return current_hash != repo.head.object.hexsha


def update_environment(
    conda_binary, repo_folder, env_file="environment.devenv.yml", local=False,
):
    """ Update conda environment. """
    env_file = Path(repo_folder) / env_file
    if not env_file.exists():
        env_file = Path(repo_folder) / "environment.yml"

    if local:
        os.environ["VEDC_DEV"] = ""

    return_code = run_command([conda_binary, "devenv", "-f", str(env_file)])

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
        src_file = (
            Path(src_folder)
            / f"{stream.device.device_uid.replace(' ', '_')}.intrinsics"
        )
        if not src_file.exists():
            logger.warning(
                f"No intrinsics for device '{stream.device.device_uid}' "
                f"found in {src_folder}"
            )
        else:
            intrinsics = load_object(str(src_file))
            resolution = tuple(stream.device.resolution)
            if str(resolution) not in intrinsics:
                logger.warning(
                    f"Intrinsics for device '{stream.device.device_uid}' "
                    f"at resolution {resolution} not found in "
                    f"{src_file}"
                )
            else:
                dst_file = Path(dst_folder) / f"{stream.name}.intrinsics"
                shutil.copyfile(src_file, dst_file)
                logger.debug(f"Copied {src_file} to {dst_file}")
