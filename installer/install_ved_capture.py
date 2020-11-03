""" Installation script for ved-capture.

This script will set up ved-capture including all of its dependencies as
well as the `vedc` command line interface.

Run with:

    $ python3 install_ved_capture.py

For a list of additional options run:

    $ python3 install_ved_capture.py --help

Copyright 2020 Peter Hausamann / The Visual Experience Database
"""
import os
from pathlib import Path
import time
import subprocess
import argparse
import urllib.request
from getpass import getuser, getpass
import logging
from select import select
import json
from distutils.version import LooseVersion
import re


__installer_version = "1.4.0"
__maintainer_email = "peter.hausamann@tum.de"

# -- LOGGING -- #
logger = logging.getLogger(Path(__file__).stem)


def init_logger(log_folder, verbose=False):
    """"""
    logger.setLevel(logging.DEBUG)

    # stream handler
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler = logging.StreamHandler()
    if verbose:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    # file handler
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s: %(message)s"
    )
    log_file_path = log_folder / (logger.name + ".log")
    file_handler = logging.FileHandler(filename=log_file_path)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    return logger


def show_welcome_message(yes=False):
    """"""
    if not yes:
        logger.info(
            "\n"
            "###################################################\n"
            "# Welcome to the VED capture installation script. #\n"
            "###################################################\n"
            "\n"
            "This script will guide you through the setup process for VED "
            "capture.\n"
            "\n"
            "You need an account at https://www.github.com for this script to "
            "work. Your account also needs to be a member of the VEDB GitHub "
            "organization."
            "\n"
        )
        answer = input(
            "Do you have a GitHub account and are a member of the "
            "VEDB organization? [y/n]: "
        )
        logger.debug(f"GitHub account prompt answer: {answer}")
        return answer == "y"

    else:
        logger.info(
            "\n"
            "###################################################\n"
            "#      VED capture installation - auto-mode.      #\n"
            "###################################################"
        )
        return True


def show_header(header, message=None, delay=1):
    """"""
    logger.info("\n" + header + "\n" + "-" * len(header))
    time.sleep(delay)

    if message is not None:
        logger.info(message)


# -- COMMAND RUNNERS -- #
def abort(exit_code=1):
    """"""
    exit(exit_code)


def log_as_warning_or_debug(data):
    """"""
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
    """"""
    logger.debug(data.rstrip(b"\n").decode("utf-8"))


def handle_process(process, command, error_msg, n_bytes=4096):
    """"""
    if process.stdout is not None:
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

    return_code = process.wait()

    if return_code != 0:
        if error_msg is None:
            logger.error(
                " ".join([str(c) for c in command])
                + f" failed with exit code {return_code}. See the output "
                f"above for more information. If you don't know how to fix "
                f"this by yourself, please send an email with the "
                f"'install_ved_capture.log' file located in "
                f"{Path(__file__).resolve().parent} to {__maintainer_email}.",
            )
        else:
            logger.error(error_msg)
        abort()


def run_command(command, error_msg=None, shell=False, f_stdout=None):
    """"""
    logger.debug(
        f"Running '{command if shell else ' '.join(str(c) for c in command)}'."
    )

    with subprocess.Popen(
        command,
        stdout=f_stdout or subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
    ) as process:
        handle_process(process, command, error_msg)


def run_as_sudo(command, password, error_message=None):
    """"""
    logger.debug(f"Running '{' '.join(str(c) for c in command)}' as sudo.")

    if password is None:
        return run_command(["sudo"] + command)
    else:
        try:
            with subprocess.Popen(
                ["sudo", "-S"] + command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                process.stdin.write(password.encode("utf-8") + b"\n")
                process.stdin.flush()
                handle_process(process, command, error_message)
        except BrokenPipeError:
            pass


def write_file_as_sudo(file_path, contents):
    """"""
    process = subprocess.Popen(
        f"sudo -S dd if=/dev/stdin of={file_path} conv=notrunc".split(),
        stdin=subprocess.PIPE,
    )
    process.communicate(contents.encode("utf-8"))


# -- GIT -- #
def check_ssh_pubkey(filename="id_ecdsa.pub"):
    """"""
    filepath = Path("~/.ssh").expanduser() / filename
    if filepath.exists():
        with open(filepath) as f:
            return f.read()
    else:
        return None


def generate_ssh_keypair(spec="-b 521 -t ecdsa", filename="id_ecdsa"):
    """"""
    filepath = Path("~/.ssh").expanduser() / filename
    run_command(
        "ssh-keygen -q -P".split() + ["", "-f", filepath] + spec.split(),
    )
    return check_ssh_pubkey(filename + ".pub")


def show_github_ssh_instructions(ssh_key):
    """"""
    logger.info(
        f"Go to https://github.com/settings/ssh/new and paste this into the "
        f"'Key' field: \n\n"
        f"{ssh_key}\n"
        f"Then, click 'Add new SSH key'.\n"
    )


def get_repo_folder(base_folder, repo_url):
    """"""
    return base_folder / repo_url.rsplit("/", 1)[-1].split(".")[0]


def get_version_or_branch(repo_folder, branch=None, default="master"):
    """"""
    if branch is not None:
        return branch

    versions = (
        subprocess.check_output(
            [
                "git",
                f"--work-tree={repo_folder}",
                f"--git-dir={repo_folder}/.git",
                "tag",
                "-l",
                "--sort",
                "-version:refname",
            ]
        )
        .decode()
        .split("\n")[:-1]
    )

    # don't match pre-releases
    pattern = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
    versions = [v for v in versions if re.match(pattern, v)]

    if len(versions) == 0:
        return default
    else:
        return versions[0]


def update_repo(repo_folder, branch):
    """"""
    branch = get_version_or_branch(repo_folder, branch)

    error_msg = (
        f"Could not update {repo_folder}. "
        f"You might need to delete the folder and try again."
    )
    run_command(
        [
            "git",
            f"--work-tree={repo_folder}",
            f"--git-dir={repo_folder}/.git",
            "fetch",
        ],
        error_msg=error_msg,
    )
    run_command(
        [
            "git",
            f"--work-tree={repo_folder}",
            f"--git-dir={repo_folder}/.git",
            "checkout",
            branch,
        ],
        error_msg=error_msg,
    )

    # merge if HEAD is not detached (i.e. we checked out a branch, not a tag)
    if (
        subprocess.call(
            [
                "git",
                f"--work-tree={repo_folder}",
                f"--git-dir={repo_folder}/.git",
                "symbolic-ref",
                "-q",
                "HEAD",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    ):
        run_command(
            [
                "git",
                f"--work-tree={repo_folder}",
                f"--git-dir={repo_folder}/.git",
                "merge",
            ],
            error_msg=error_msg,
        )


def clone_repo(base_folder, repo_folder, repo_url, branch=None):
    """"""
    base_folder.mkdir(parents=True, exist_ok=True)
    error_msg = "Could not clone the repository. Did you set up the SSH key?"
    run_command(["git", "clone", repo_url, repo_folder], error_msg=error_msg)
    update_repo(repo_folder, branch)


def verify_latest_version(vedc_repo_folder):
    """"""
    repo_script = vedc_repo_folder / "installer" / "install_ved_capture.py"

    installer_version = LooseVersion(__installer_version)
    with open(repo_script, "rt") as f:
        repo_script_version = LooseVersion(
            re.search(
                r"^__installer_version = ['\"]([^'\"]*)['\"]", f.read(), re.M
            ).group(1)
        )

    if installer_version < repo_script_version:
        show_header("ERROR")
        logger.error(
            f"You are using an outdated version of the installer script. "
            f"Please run:\n\n"
            f"python3 {repo_script}"
        )
        abort()


# -- SYSTEM DEPS -- #
def password_prompt():
    """"""
    show_header("Installing system-wide dependencies")
    logger.info(
        "Some things need to be configured system wide. In order for "
        "this to work, the current user must have root access to the "
        "machine. You will need to enter your password once. The password "
        "will not be stored anywhere.\n"
    )
    password = getpass("Please enter your password now:")

    return password


def configure_spinnaker(password, groupname="flirimaging"):
    """"""
    # Create flir group
    run_as_sudo(["groupadd", "-f", groupname], password)
    run_as_sudo(["usermod", "-a", "-G", groupname, getuser()], password)

    # Create udev rules
    udev_file = "/etc/udev/rules.d/40-flir-spinnaker.rules"
    udev_rules = (
        f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="1e10", '
        f'GROUP="{groupname}"\n'
    )
    run_as_sudo(["rm", "-f", udev_file], password)
    write_file_as_sudo(udev_file, udev_rules)

    # Restart udev daemon
    run_as_sudo(["/etc/init.d/udev", "restart"], password)

    # Increase USB-FS size
    old_params = '"quiet splash"'
    new_params = '"quiet splash usbcore.usbfs_memory_mb=1000"'
    run_as_sudo(
        [
            "sed",
            "-i",
            f"s/GRUB_CMDLINE_LINUX_DEFAULT={old_params}"
            f"/GRUB_CMDLINE_LINUX_DEFAULT={new_params}/",
            "/etc/default/grub",
        ],
        password,
    )
    run_as_sudo(["update-grub"], password)


def configure_libuvc(password):
    """"""
    udev_file = "/etc/udev/rules.d/10-libuvc.rules"
    udev_rules = (
        'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", '
        'GROUP="plugdev", MODE="0664"\n'
    )
    run_as_sudo(["rm", "-f", udev_file], password)
    write_file_as_sudo(udev_file, udev_rules)

    run_as_sudo(["udevadm", "trigger"], password)


# -- CONDA -- #
def install_miniconda(prefix="~/miniconda3"):
    """"""
    prefix = Path(prefix).expanduser()

    filename, _ = urllib.request.urlretrieve(
        "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    )

    run_command(["/bin/bash", filename, "-b", "-p", str(prefix)])


def get_min_conda_devenv_version(repo_folder):
    """ Get minimum conda devenv version. """
    with open(Path(repo_folder) / "environment.devenv.yml") as f:
        for line in f:
            pattern = re.compile(r'{{ min_conda_devenv_version\("(.+)"\) }}')
            result = re.search(pattern, line)
            if result:
                return result.group(1)
        else:
            return "2.1.1"


def create_environment(
    conda_binary, mamba_binary, vedc_repo_folder, config_folder
):
    """ Create env. """
    # Install mamba and conda devenv
    run_command(
        [
            mamba_binary if mamba_binary.exists() else conda_binary,
            "install",
            "-y",
            "-c",
            "conda-forge",
            f"conda-devenv>={get_min_conda_devenv_version(vedc_repo_folder)}",
            "mamba",
        ]
    )

    devenv_file = vedc_repo_folder / "environment.devenv.yml"
    if devenv_file.exists():
        os.environ["VEDCDIR"] = str(config_folder)
        if config_folder != Path("~/.config/vedc").expanduser():
            # Can't use mamba yet if config folder is not in default location
            run_command([conda_binary, "devenv", "-f", devenv_file])
            return
        else:
            # Update environment.yml with conda devenv
            try:
                (vedc_repo_folder / "environment.yml").unlink()
            except FileNotFoundError:
                pass
            with open(vedc_repo_folder / "environment.yml", "w") as f:
                run_command(
                    [conda_binary, "devenv", "-f", devenv_file, "--print"],
                    f_stdout=f,
                )

    # Update environment with mamba
    run_command(
        [
            mamba_binary,
            "env",
            "update",
            "-f",
            vedc_repo_folder / "environment.yml",
        ]
    )


def write_paths(
    conda_binary,
    conda_script,
    mamba_binary,
    vedc_repo_folder,
    config_folder="~/.config/vedc",
    pri_path=None,
):
    """"""
    paths = {
        "installer_version": __installer_version,
        "conda_binary": str(conda_binary),
        "conda_script": str(conda_script),
        "mamba_binary": str(mamba_binary),
        "vedc_repo_folder": str(vedc_repo_folder),
    }

    if pri_path is not None:
        paths["pri_path"] = str(Path(args.pri_path).expanduser().resolve())

    config_folder = Path(config_folder).expanduser()
    config_folder.mkdir(parents=True, exist_ok=True)
    json_file = config_folder / "paths.json"
    logger.debug(f"Writing paths to {json_file}")

    with open(json_file, "w") as f:
        f.write(json.dumps(paths))


if __name__ == "__main__":

    # Parse command line arguments
    parser = argparse.ArgumentParser("install_ved_capture.py")
    parser.add_argument(
        "-f",
        "--folder",
        default="~/vedb",
        help="Base folder for installation",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Install non-interactively",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show debug output on the command line",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="Install from the parent folder instead of the remote repository",
    )
    parser.add_argument(
        "-b", "--branch", default=None, help="Install from this branch or tag",
    )
    parser.add_argument(
        "-c",
        "--config_folder",
        default="~/.config/vedc",
        help="Path to the application config folder",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="Update conda environment instead of reinstalling",
    )
    parser.add_argument(
        "--miniconda_prefix",
        default="{base_folder}/miniconda3",
        help="Base folder for miniconda installation",
    )
    parser.add_argument(
        "--pri_branch",
        default=None,
        help="Install pupil_recording_interface from this branch or tag",
    )
    parser.add_argument(
        "--pri_path",
        default=None,
        help="Path to local pupil_recording_interface repository",
    )
    parser.add_argument(
        "--no_ssh", action="store_true", help="Disable check for SSH key",
    )
    parser.add_argument(
        "--no_root",
        action="store_true",
        help="Skip steps that require root access",
    )
    parser.add_argument(
        "--no_version_check",
        action="store_true",
        help="Skip checking for newer install script version",
    )
    args = parser.parse_args()

    # Set up logger
    logger = init_logger(Path(__file__).parent, verbose=args.verbose)

    # check args
    if args.pri_branch and args.pri_path:
        logger.error(
            "You cannot provide --pri_branch and --pri_path at the same time."
        )
        abort()

    # Set up paths
    base_folder = Path(args.folder).expanduser().resolve()
    vedc_repo_url = f"ssh://git@github.com/vedb/ved-capture"
    if args.local:
        vedc_repo_folder = Path(__file__).resolve().parents[1]
    else:
        vedc_repo_folder = get_repo_folder(base_folder, vedc_repo_url)
    config_folder = Path(
        args.config_folder.format(repo_folder=vedc_repo_folder)
    ).expanduser()

    miniconda_prefix = Path(
        args.miniconda_prefix.format(base_folder=base_folder)
    ).expanduser()
    conda_binary = miniconda_prefix / "bin" / "conda"
    conda_script = miniconda_prefix / "etc" / "profile.d" / "conda.sh"
    mamba_binary = miniconda_prefix / "condabin" / "mamba"

    # Make sure that not running from activated conda env
    if (
        "CONDA_PREFIX" in os.environ
        and Path(os.environ["CONDA_PREFIX"]) != miniconda_prefix
    ):
        logger.error(
            "You are running the installer from an activated conda "
            "environment. Please run 'conda deactivate' and try again."
        )
        abort()

    # Make sure git is installed
    if subprocess.call(["which", "git"], stdout=subprocess.DEVNULL) != 0:
        logger.error(
            "git not found. Please run 'sudo apt install git' and try again."
        )
        abort()

    # Welcome message
    if not show_welcome_message(args.yes):
        logger.info(
            f"\nPlease create an account at https://www.github.com and send "
            f"an email with your user name to {__maintainer_email} to get "
            f"access.",
        )
        abort()

    # Check SSH key
    ssh_key = check_ssh_pubkey()
    if ssh_key is None and not args.no_ssh:
        show_header("Generating SSH keypair")
        ssh_key = generate_ssh_keypair()
        if ssh_key is None:
            logger.error("Could not generate SSH keypair")
            abort()
        show_github_ssh_instructions(ssh_key)
        if args.yes:
            logger.info("When you're done, run this script again.")
            abort()
        else:
            input("When you're done, press Enter.\n")

    # Clone or update repository
    if not vedc_repo_folder.exists():
        show_header(
            "Cloning repository",
            f"Retrieving git repository from {vedc_repo_url}",
        )
        clone_repo(base_folder, vedc_repo_folder, vedc_repo_url, args.branch)
    elif not args.local:
        show_header(
            "Updating repository", f"Pulling new changes from {vedc_repo_url}"
        )
        update_repo(vedc_repo_folder, args.branch)

    # Check script version
    if not args.no_version_check:
        verify_latest_version(vedc_repo_folder)

    # Install miniconda if necessary
    if not conda_binary.exists():
        show_header(
            "Installing miniconda", f"Install location: {miniconda_prefix}",
        )
        install_miniconda(miniconda_prefix)
    else:
        logger.debug(
            f"Conda binary found at {conda_binary}. Skipping miniconda "
            f"install."
        )

    # Create or update environment
    if args.pri_branch:
        os.environ["PRI_PIN"] = args.pri_branch
    if args.pri_path:
        os.environ["PRI_PATH"] = str(
            Path(args.pri_path).expanduser().resolve()
        )
    if args.local:  # TODO: rename flag to develop or introduce new flag
        os.environ["VEDC_DEV"] = ""

    env_path = miniconda_prefix / "envs" / "vedc"
    if not args.update and env_path.exists():
        run_command([conda_binary, "env", "remove", "-n", "vedc"])

    show_header(
        "Creating environment", "This will take a couple of minutes. ☕",
    )
    create_environment(
        conda_binary, mamba_binary, vedc_repo_folder, config_folder
    )

    # Steps with root access
    if not args.no_root:

        # Get password for sudo stuff
        if not args.yes:
            password = password_prompt()
        else:
            password = None

        # Configure USB settings
        show_header("Configuring USB settings")
        configure_spinnaker(password)
        configure_libuvc(password)

        # Create link to vedc binary
        show_header("Installing command line interface")
        vedc_binary = "/usr/local/bin/vedc"
        show_header(
            "Creating vedc excecutable", f"Installing to {vedc_binary}.",
        )
        run_as_sudo(["rm", "-f", vedc_binary], password)
        write_file_as_sudo(
            vedc_binary,
            f"#!/bin/bash\n"
            f'. {conda_script} && conda activate vedc && vedc "$@"\n',
        )
        run_as_sudo(["chmod", "+x", vedc_binary], password)

    else:
        logger.debug("Skipping steps with root access.")

    # Write paths
    write_paths(
        conda_binary,
        conda_script,
        mamba_binary,
        vedc_repo_folder,
        config_folder,
        args.pri_path,
    )

    # symlink config folder
    if not args.local:
        symlink = base_folder / "config"
        if not symlink.exists():
            symlink.symlink_to(config_folder, target_is_directory=True)

    # Check installation
    show_header("Checking installation")
    if not args.no_root:
        if args.verbose:
            run_command(["vedc", "check_install", "-v"])
        else:
            run_command(["vedc", "check_install"])
    else:
        run_command(
            f"/bin/bash -c '. {conda_script} && conda activate vedc "
            f"&& vedc check_install'",
            shell=True,
        )

    # Success
    logger.info("Installation successful. Congratulations! 🎉🎉🎉")
    if not args.no_root:
        logger.info("Please reboot your system.")
