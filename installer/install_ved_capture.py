""""""
import os
import time
import subprocess
import argparse
import urllib.request
from getpass import getuser, getpass
from glob import glob
import logging
from select import select


__installer_version = "0.1.0"
__vedc_version = None  # TODO set this once there is a first release
__maintainer_email = "peter.hausamann@tum.de"


# -- LOGGING -- #
def init_logger(log_folder, name="install_ved_capture", verbose=False):
    """"""
    logger = logging.getLogger(name)
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
    log_file_path = os.path.join(log_folder, name + ".log")
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
            "Do you have a GitHub account that is member of the "
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
    os.chdir(initial_folder)
    exit(exit_code)


def log_as_warning_or_debug(data):
    """"""
    _suppress_if_startswith = (
        b"[sudo] ",
        b"Extracting : ",
        b"==> WARNING: A newer version of conda exists. <==",
    )

    _suppress_if_endswith = (
        b"is not a symbolic link",
    )

    data = data.rstrip(b"\n")

    if (
        data.startswith(_suppress_if_startswith)
        or data.endswith(_suppress_if_endswith)
    ):
        logger.debug(data.decode("utf-8"))
    else:
        logger.warning(data.decode("utf-8"))


def log_as_debug(data):
    """"""
    logger.debug(data.rstrip(b"\n").decode("utf-8"))


def handle_process(process, command, error_msg, n_bytes=4096):
    """"""
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

    return_code = process.wait()

    if return_code != 0:
        if error_msg is None:
            logger.error(
                " ".join(command) +
                f" failed with exit code {return_code}. See the output above "
                f"for more information. If you don't know how to fix this by "
                f"yourself, please send an email with the "
                f"'install_ved_capture.log' file located in {initial_folder} "
                f"to {__maintainer_email}.",
            )
        else:
            logger.error(error_msg)
        abort()


def run_command(command, error_msg=None, shell=False):
    """"""
    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell,
    ) as process:
        handle_process(process, command, error_msg)


def run_as_sudo(command, password, error_message=None):
    """"""
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
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return f.read()
    else:
        return None


def generate_ssh_keypair(spec="-b 521 -t ecdsa", filename="id_ecdsa"):
    """"""
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)
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
    return os.path.join(base_folder, repo_url.rsplit("/", 1)[-1].split(".")[0])


def clone_repo(base_folder, repo_url):
    """"""
    os.makedirs(base_folder, exist_ok=True)
    os.chdir(base_folder)
    error_msg = (
        "Could not clone the repository. Did you set up the SSH key?"
    )
    run_command(["git", "clone", repo_url], error_msg=error_msg)


def update_repo(repo_folder):
    """"""
    os.chdir(repo_folder)
    error_msg = (
        f"Could not update {repo_folder}. "
        f"You might need to delete the folder and try again."
    )
    run_command(["git", "pull"], error_msg=error_msg)


# -- SYSTEM DEPS -- #
def password_prompt():
    """"""
    show_header("Installing system-wide dependencies")
    logger.info(
        "Some dependencies need to be installed system wide. In order for "
        "this to work, the current user must have root access to the "
        "machine. You will need to enter your password once. The password "
        "will not be stored anywhere.\n"
    )
    password = getpass("Please enter your password now:")

    return password


def install_spinnaker_sdk(folder, password, groupname="flirimaging"):
    """"""
    # Install dependencies
    run_as_sudo(
        ["apt", "install", "libswscale-dev", "libavcodec-dev"], password,
    )

    # Install packages
    deb_files = glob(os.path.join(folder, "*.deb"))
    run_as_sudo(["dpkg", "-i"] + deb_files, password)

    # Create flir group
    run_as_sudo(["groupadd", "-f", groupname], password)
    run_as_sudo(["usermod", "-a", "-G", groupname, getuser()], password)

    # Create udev rules
    udev_file = "/etc/udev/rules.d/40-flir-spinnaker.rules"
    udev_rules = f"SUBSYSTEM==\"usb\", ATTRS{{idVendor}}==\"1e10\", " \
                 f"GROUP=\"{groupname}\"\n"
    write_file_as_sudo(udev_file, udev_rules)

    # Restart udev daemon
    run_as_sudo(["/etc/init.d/udev", "restart"], password)


def install_libuvc_deps(password):
    """"""
    # Install libudev0
    filename, _ = urllib.request.urlretrieve(
        "http://mirrors.kernel.org/ubuntu/pool/main/u/udev/"
        "libudev0_175-0ubuntu9_amd64.deb"
    )

    run_as_sudo(["dpkg", "-i", filename], password)

    # Create udev rules
    udev_file = "/etc/udev/rules.d/10-libuvc.rules"
    udev_rules = "SUBSYSTEM==\"usb\", ENV{DEVTYPE}==\"usb_device\", " \
                "GROUP=\"plugdev\", MODE=\"0664\"\n"
    write_file_as_sudo(udev_file, udev_rules)

    run_as_sudo(["udevadm", "trigger"], password)


# -- CONDA -- #
def install_miniconda(prefix="~/miniconda3"):
    """"""
    prefix = os.path.expanduser(prefix)

    filename, _ = urllib.request.urlretrieve(
        "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    )

    run_command(["bash", filename, "-b", "-p", prefix])


if __name__ == "__main__":

    # Parse command line arguments
    parser = argparse.ArgumentParser("install_ved_capture.py")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="set this flag to install non-interactively",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="set this flag to show debug output",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="set this flag to install from the parent folder instead of the "
             "remote repository",
    )
    parser.add_argument(
        "--no_ssh",
        action="store_true",
        help="set this flag to disable check for SSH key",
    )
    parser.add_argument(
        "--no_root",
        action="store_true",
        help="set this flag to skip steps that require root access",
    )
    parser.add_argument(
        "-f",
        "--folder",
        default="~/vedb",
        help="base folder for installation",
    )
    parser.add_argument(
        "--miniconda_prefix",
        default="{base_folder}/miniconda3",
        help="prefix for miniconda installation",
    )
    args = parser.parse_args()

    # Set up paths
    base_folder = os.path.expanduser(args.folder)
    vedc_repo_url = "ssh://git@github.com/vedb/ved-capture"
    if __vedc_version is not None:
        vedc_repo_url += f"@v{__vedc_version}"
    if args.local:
        vedc_repo_folder = os.path.join(os.path.dirname(__file__), os.pardir)
    else:
        vedc_repo_folder = get_repo_folder(base_folder, vedc_repo_url)

    miniconda_prefix = os.path.expanduser(
        args.miniconda_prefix.format(base_folder=base_folder),
    )
    conda_binary = os.path.join(miniconda_prefix, "bin", "conda")
    conda_script = os.path.join(
        miniconda_prefix, "etc", "profile.d", "conda.sh",
    )

    initial_folder = os.getcwd()

    # Set up logger
    logger = init_logger(os.path.dirname(__file__), verbose=args.verbose)

    # Welcome message
    if not show_welcome_message(args.yes):
        logger.info(
            "Please contact someone from the VEDB team to give you access.",
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
            input("When you're done, press Enter.")
            logger.info("")

    # Clone or update repository
    if not os.path.exists(vedc_repo_folder):
        show_header(
            "Cloning repository",
            f"Retrieving git repository from {vedc_repo_url}"
        )
        clone_repo(base_folder, vedc_repo_url)
    elif not args.local:
        show_header(
            "Updating repository",
            f"Pulling new changes from {vedc_repo_url}"
        )
        update_repo(vedc_repo_folder)

    os.chdir(vedc_repo_folder)

    # Steps with root access
    if not args.no_root:

        # Get password for sudo stuff
        if not args.yes:
            password = password_prompt()
        else:
            password = None

        # Install Spinnaker SDK
        show_header(
            "Installing Spinnaker SDK", "This may take a couple of minutes.",
        )
        sdk_folder = os.path.join(
            vedc_repo_folder, "installer", "spinnaker_sdk_1.27.0.48_amd64",
        )
        install_spinnaker_sdk(sdk_folder, password)

        # Create udev rules for libuvc
        show_header("Installing libuvc dependencies")
        install_libuvc_deps(password)

    else:
        logger.debug("Skipping installation of system-wide dependencies.")

    # Install miniconda if necessary
    if not os.path.exists(conda_binary):
        show_header(
            "Installing miniconda", "This may take a couple of minutes.",
        )
        install_miniconda(miniconda_prefix)
    else:
        logger.debug(
            f"Conda binary found at {conda_binary}. Skipping miniconda "
            f"install."
        )

    # Create or update environment
    if not os.path.exists(os.path.join(miniconda_prefix, "envs", "vedc")):
        show_header(
            "Creating environment", "This may take a couple of minutes.",
        )
        run_command([conda_binary, "env", "create"])
    else:
        show_header(
            "Updating environment", "This may take a couple of minutes.",
        )
        run_command([conda_binary, "env", "update"])

    if args.local:
        run_command(
            f"/bin/bash -c '. {conda_script} && conda activate vedc "
            f"&& pip install --no-deps -U -e {vedc_repo_folder}'",
            shell=True,
        )

    # Create link to vedc binary
    if not args.no_root:
        vedc_binary = "/usr/local/bin/vedc"
        show_header(
            "Creating vedc excecutable", f"Installing to {vedc_binary}.",
        )
        write_file_as_sudo(
            vedc_binary,
            f"#!/bin/bash\n"
            f". {conda_script} && conda activate vedc && vedc \"$@\"\n"
        )
        run_as_sudo(["chmod", "+x", vedc_binary], password)
    else:
        logger.debug("Skipping installation of vedc binary.")

    # Check installation
    show_header("Checking installation")
    if args.verbose:
        run_command(["vedc", "check_install", "-v"])
    else:
        run_command(["vedc", "check_install"])

    # Success
    os.chdir(initial_folder)
    logger.info("\nInstallation successful. Congratulations! 🎉🎉🎉")
