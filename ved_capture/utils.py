""""""
import os
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from select import select

import numpy as np
import simpleaudio
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


def run_command(command, shell=False, f_stdout=None, n_bytes=4096):
    """ Run system command and pipe output to logger. """
    with subprocess.Popen(
        command,
        stdout=f_stdout or subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
    ) as process:
        if f_stdout is None:
            readable = {
                process.stdout.fileno(): log_as_debug,
                process.stderr.fileno(): log_as_warning_or_debug,
            }
        else:
            readable = {
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


def get_paths(config_dir=None):
    """ Get dictionary with application paths. """
    config_dir = Path(config_dir or ConfigParser.config_dir())
    try:
        with open(config_dir / "paths.json") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return None


def write_paths(paths, config_dir=None):
    """ Write dictionary with application paths. """
    config_dir = Path(config_dir or ConfigParser.config_dir())
    with open(config_dir / "paths.json", "w") as f:
        f.write(json.dumps(paths))


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
    if not isinstance(branch, git.TagReference):
        repo.git.merge()

    # Return True if the repo was updated
    return current_hash != repo.head.object.hexsha


def get_min_conda_devenv_version(devenv_file):
    """ Get minimum conda devenv version. """
    with open(devenv_file) as f:
        for line in f:
            pattern = re.compile('{{ min_conda_devenv_version\("(.+)"\) }}')
            result = re.search(pattern, line)
            if result:
                return result.group(1)
        else:
            return "2.1.1"


def update_environment(
    paths,
    devenv_file="environment.devenv.yml",
    local=False,
    pri_branch=None,
    pri_path=None,
):
    """ Update conda environment. """
    devenv_file = Path(paths["vedc_repo_folder"]) / devenv_file
    env_file = Path(paths["vedc_repo_folder"]) / "environment.yml"
    if not devenv_file.exists():
        devenv_file = env_file

    if local:
        os.environ["VEDC_DEV"] = ""
    if pri_branch:
        os.environ["PRI_PIN"] = pri_branch
    if pri_path:
        paths["pri_path"] = str(Path(pri_path).expanduser().resolve())
        write_paths(paths)

    # Only install PRI from local repo if pri_branch isn't set but local or
    # pri_path is
    if not pri_branch and "pri_path" in paths and (local or pri_path):
        os.environ["PRI_PATH"] = paths["pri_path"]

    # Install mamba if missing
    if "mamba_binary" not in paths:
        logger.info("Installing mamba. 🐍")
        run_command(
            [
                paths["conda_binary"],
                "install",
                "-y",
                "-c",
                "conda-forge",
                "mamba",
            ]
        )
        paths["mamba_binary"] = str(
            Path(paths["conda_binary"]).parents[1] / "condabin" / "mamba"
        )
        write_paths(paths)

    # Update conda devenv
    return_code = run_command(
        [
            paths["mamba_binary"],
            "install",
            "-y",
            "-c",
            "conda-forge",
            f"conda-devenv>={get_min_conda_devenv_version(devenv_file)}",
        ]
    )
    if return_code != 0:
        return return_code

    if (
        "VECDIR" in os.environ
        and Path(os.environ["VEDCDIR"]) != Path("~/.config/vedc").expanduser()
    ):
        # Can't use mamba yet if config folder is not in default location
        return run_command(
            [paths["conda_binary"], "devenv", "-f", devenv_file]
        )
    else:
        # Update environment.yml with conda devenv
        try:
            env_file.unlink()
        except FileNotFoundError:
            pass
        with open(env_file, "w") as f:
            return_code = run_command(
                [
                    paths["conda_binary"],
                    "devenv",
                    "-f",
                    devenv_file,
                    "--print",
                ],
                f_stdout=f,
            )
            if return_code != 0:
                return return_code

    # Update environment with mamba
    return_code = run_command(
        [paths["mamba_binary"], "env", "update", "-f", str(env_file)]
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
        src_file = (
            Path(src_folder)
            / f"{str(stream.device.device_uid).replace(' ', '_')}.intrinsics"
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


def beep(freq=440, fs=44100, seconds=0.1):
    """ Make a beep noise to indicate recording state. """

    t = np.linspace(0, seconds, int(fs * seconds))

    if seconds > 0.02:
        fade_len = int(fs * 0.01)
        fade_window = np.hstack(
            (
                np.hanning(fade_len)[: fade_len // 2],
                np.ones(len(t) - fade_len),
                np.hanning(fade_len)[fade_len // 2 :],
            )
        )
    else:
        fade_window = 1

    if not isinstance(freq, list):
        freq = [freq]

    notes = np.hstack([np.sin(f * t * 2 * np.pi) * fade_window for f in freq])
    audio = (notes * (2 ** 15 - 1) / np.max(np.abs(notes))).astype(np.int16)

    simpleaudio.play_buffer(audio, 1, 2, fs)
    time.sleep(len(freq) * seconds)
