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
from simpleaudio._simpleaudio import SimpleaudioError
from pkg_resources import parse_version

import git
import pupil_recording_interface as pri
from pupil_recording_interface.externals.file_methods import load_object

from ved_capture.config import ConfigParser

logger = logging.getLogger(__name__)


def log_as_warning_or_debug(data):
    """ Log message as warning, unless it's known to be a debug message. """
    _suppress_if_startswith = (
        "[sudo] ",
        'Please run using "bash" or "sh"',
        "==> WARNING: A newer version of conda exists. <==",
    )

    _suppress_if_endswith = ("is not a symbolic link",)

    _suppress_if_contains = ("Extracting : ",)

    try:
        data = data.strip(b"\n").decode("utf-8")
    except UnicodeDecodeError:
        logger.debug("!!Error decoding process output!!")
        return

    if (
        data.startswith(_suppress_if_startswith)
        or data.endswith(_suppress_if_endswith)
        or any(data.find(s) for s in _suppress_if_contains)
    ):
        logger.debug(data)
    else:
        logger.warning(data)


def log_as_debug(data):
    """ Log message as debug. """
    try:
        data = data.rstrip(b"\n").decode("utf-8")
        logger.debug(data)
    except UnicodeDecodeError:
        logger.debug("!!Error decoding process output!!")


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
    if not repo.head.is_detached:
        repo.git.merge()

    # Return True if the repo was updated
    return current_hash != repo.head.object.hexsha


def get_min_conda_devenv_version(devenv_file):
    """ Get minimum conda devenv version. """
    with open(devenv_file) as f:
        for line in f:
            pattern = re.compile(r'{{ min_conda_devenv_version\("(.+)"\) }}')
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
    conda_prefix = Path(paths["conda_binary"]).parents[1]
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

    # TODO hacky way of installing to base environment
    os.environ["CONDA_PREFIX"] = str(conda_prefix)

    # Install mamba if missing
    if "mamba_binary" not in paths or not Path(paths["mamba_binary"]).exists():
        logger.info("Installing mamba. 🐍")
        run_command(
            [
                paths["conda_binary"],
                "install",
                "-y",
                "-c",
                "conda-forge",
                "-n",
                "base",
                "mamba",
            ]
        )
        paths["mamba_binary"] = str(conda_prefix / "condabin" / "mamba")
        write_paths(paths)

    # Update conda devenv
    return_code = run_command(
        [
            paths["mamba_binary"],
            "install",
            "-y",
            "-c",
            "conda-forge",
            "-n",
            "base",
            f"conda-devenv>={get_min_conda_devenv_version(devenv_file)}",
        ]
    )
    if return_code != 0:
        return return_code

    if (
        "VEDCDIR" in os.environ
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


def _copy_cam_params(
    stream,
    src_folder,
    dst_folder,
    param_type="intrinsics",
    suffix="",
    stereo=False,
):
    """ Copy a single intrinsics or extrinsics file. """
    src_file = (
        Path(src_folder) / f"{str(stream.device.device_uid).replace(' ', '_')}"
        f"{suffix}.{param_type}"
    )
    if not src_file.exists():
        logger.warning(
            f"No {param_type} for device '{stream.device.device_uid}' "
            f"found in {src_file.parent}"
        )
    else:
        params = load_object(str(src_file))
        resolution = tuple(stream.device.resolution)
        if stereo:
            resolution = (resolution[0] // 2, resolution[1])
        if str(resolution) not in params:
            logger.warning(
                f"{param_type.capitalize()} for device "
                f"'{stream.device.device_uid}' at resolution {resolution} "
                f"not found in {src_file}"
            )
        else:
            dst_file = Path(dst_folder) / f"{stream.name}{suffix}.{param_type}"
            shutil.copyfile(src_file, dst_file)
            logger.debug(f"Copied {src_file} to {dst_file}")


def copy_cam_params(
    streams, src_folder, dst_folder, intrinsics=None, extrinsics=None
):
    """ Copy camera parameters. """
    intrinsics = intrinsics or [
        name for name, s in streams.items() if isinstance(s, pri.VideoStream)
    ]
    extrinsics = extrinsics or [
        name for name, s in streams.items() if isinstance(s, pri.VideoStream)
    ]

    for stream_name in intrinsics:
        if stream_name in streams:
            stream = streams[stream_name]
            if isinstance(stream.device, pri.RealSenseDeviceT265):
                if stream.device.video != "left":
                    _copy_cam_params(
                        stream,
                        src_folder,
                        dst_folder,
                        "intrinsics",
                        "_right",
                        stereo=stream.device.video != "right",
                    )
                if stream.device.video != "right":
                    _copy_cam_params(
                        stream,
                        src_folder,
                        dst_folder,
                        "intrinsics",
                        "_left",
                        stereo=stream.device.video != "left",
                    )
            else:
                _copy_cam_params(stream, src_folder, dst_folder, "intrinsics")

    for stream_name in extrinsics:
        if stream_name in streams:
            stream = streams[stream_name]
            if isinstance(stream.device, pri.RealSenseDeviceT265):
                if stream.device.video != "left":
                    _copy_cam_params(
                        stream,
                        src_folder,
                        dst_folder,
                        "extrinsics",
                        "_right",
                        stereo=stream.device.video != "right",
                    )
                if stream.device.video != "right":
                    _copy_cam_params(
                        stream,
                        src_folder,
                        dst_folder,
                        "extrinsics",
                        "_left",
                        stereo=stream.device.video != "left",
                    )
            else:
                _copy_cam_params(stream, src_folder, dst_folder, "extrinsics")


def beep(freq=440, fs=44100, seconds=0.1, fade_len=0.01):
    """ Make a beep noise to indicate recording state. """

    t = np.linspace(0, seconds, int(fs * seconds))

    if seconds > 2 * fade_len:
        fade_len = int(fs * fade_len)
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

    try:
        play_obj = simpleaudio.play_buffer(audio, 1, 2, fs)  # noqa
        # TODO play_obj.wait_done() blocks if there's an error
        time.sleep(len(freq) * seconds)
    except SimpleaudioError as e:
        logger.error(f"Error playing sound: {e}")


def check_disk_space(folder, min_space_gb=30):
    """ Check available disk space and emit a warning if low. """
    try:
        free_gb = shutil.disk_usage(folder).free / (1024 ** 3)
    except FileNotFoundError:
        logger.warning(f"Could not determine disk space for folder {folder}")
        return

    if free_gb < min_space_gb:
        logger.warning(
            f"Available disk space in {folder} is {free_gb:.1f} GB, make sure "
            f"you have at least {min_space_gb} GB of free space"
        )
