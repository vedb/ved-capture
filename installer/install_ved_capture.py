""""""
import os
import time
import subprocess
import argparse
import urllib.request
from getpass import getuser, getpass
from glob import glob


def show_welcome_message(yes=False):
    """"""
    if yes:
        print(
            "###################################################\n"
            "#      VED capture installation - auto-mode.      #\n"
            "###################################################"
        )
        return True

    else:
        print(
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
        return answer == "y"


def show_header(message, timeout=0.1):
    """"""
    print("\n" + message + "\n" + "-" * len(message))
    time.sleep(timeout)


def check_ssh_pubkey(filename="id_ecdsa.pub"):
    """"""
    # TODO also check for private key
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return f.read()
    else:
        return None


def generate_ssh_keypair(spec="-b 521 -t ecdsa", filename="id_ecdsa"):
    """"""
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)

    try:
        subprocess.run(
            "ssh-keygen -q -P".split() + ["", "-f", filepath] + spec.split(),
            check=True,
        )
        return check_ssh_pubkey(filename + ".pub")
    except subprocess.CalledProcessError:
        return None


def show_github_ssh_instructions(ssh_key):
    """"""
    print(
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
    # Create the base folder for all VEDB software
    os.makedirs(base_folder, exist_ok=True)
    os.chdir(base_folder)

    try:
        # TODO pipe stdout to logger
        subprocess.run(
            ["git", "clone", repo_url], check=True, stdout=subprocess.DEVNULL,
        )
        # TODO get from stdout
        return True, get_repo_folder(base_folder, repo_url)
    except subprocess.CalledProcessError as e:
        return False, e.output


def update_repo(repo_folder):
    """"""
    os.chdir(repo_folder)

    try:
        # TODO pipe stdout to logger
        subprocess.run(
            ["git", "pull"], check=True, stdout=subprocess.DEVNULL,
        )
        return True, None
    except subprocess.CalledProcessError as e:
        return True, e.output


def password_prompt():
    """"""
    show_header("Installing system-wide dependencies")
    print(
        "Some dependencies need to be installed system wide. In order for "
        "this to work, the current user must have root access to the "
        "machine. You will need to enter your password once. The password "
        "will not be stored anywhere.\n"
    )
    password = getpass("Please enter your password now:")

    return password


def run_as_sudo(command, password):
    """"""
    if password is not None:
        # TODO pipe stdout to logger
        process = subprocess.Popen(
            ["sudo", "-S"] + command, stdin=subprocess.PIPE
        )
        process.communicate(password.encode("utf-8") + b"\n")
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
    else:
        # TODO pipe stdout to logger
        subprocess.run(["sudo"] + command, check=True)


def install_spinnaker_sdk(folder, password, groupname="flirimaging"):
    """"""
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
    process = subprocess.Popen(
        ['sudo', '-S', 'dd', 'if=/dev/stdin', f'of={udev_file}',
         'conv=notrunc', 'oflag=append'],
        stdin=subprocess.PIPE,
    )
    process.communicate(udev_rules.encode("utf-8"))

    # Restart udev daemon
    run_as_sudo(["/etc/init.d/udev", "restart"], password)


def create_libuvc_udev_rules(password):
    """"""
    udev_file = "/etc/udev/rules.d/10-libuvc.rules"
    udev_rules = "SUBSYSTEM==\"usb\", ENV{DEVTYPE}==\"usb_device\", " \
                "GROUP=\"plugdev\", MODE=\"0664\"\n"
    process = subprocess.Popen(
        ['sudo', '-S', 'dd', 'if=/dev/stdin', f'of={udev_file}',
         'conv=notrunc', 'oflag=append'],
        stdin=subprocess.PIPE,
    )
    process.communicate(udev_rules.encode("utf-8"))

    run_as_sudo(["udevadm", "trigger"], password)


def install_miniconda(prefix="~/miniconda3"):
    """"""
    prefix = os.path.expanduser(prefix)

    filename, _ = urllib.request.urlretrieve(
        "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    )

    cmd = ["bash", filename, "-b", "-p", prefix]
    # TODO pipe stdout to logger
    subprocess.run(cmd, stdout=subprocess.DEVNULL)


def abort(initial_folder, exit_code=1):
    """"""
    os.chdir(initial_folder)
    exit(exit_code)


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
        "--no_ssh",
        action="store_true",
        help="set this flag disable check for ECDSA key",
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
    vedc_repo_folder = get_repo_folder(base_folder, vedc_repo_url)

    miniconda_prefix = os.path.expanduser(
        args.miniconda_prefix.format(base_folder=base_folder),
    )
    conda_binary = os.path.join(miniconda_prefix, "bin", "conda")
    conda_script = os.path.join(
        miniconda_prefix, "etc", "profile.d", "conda.sh",
    )

    initial_folder = os.getcwd()

    # Welcome message
    if not show_welcome_message(args.yes):
        print(
            "Please contact someone from the VEDB team to give you access."
        )
        abort(initial_folder)

    # Check SSH key
    ssh_key = check_ssh_pubkey()
    if ssh_key is None and not args.no_ssh:
        show_header("Generating ECDSA key")
        ssh_key = generate_ssh_keypair()
        show_github_ssh_instructions(ssh_key)
        if args.yes:
            print("When you're done, run this script again.")
            abort(initial_folder)
        else:
            input("When you're done, press Enter.")
            print("")

    # Clone or update repository
    if not os.path.exists(vedc_repo_folder):
        show_header("Cloning repository")
        clone_success, _ = clone_repo(base_folder, vedc_repo_url)
        if not clone_success:
            print(
                "ERROR: Could not clone the repository. Did you set up the "
                "SSH key?"
            )
            show_github_ssh_instructions(ssh_key)
            abort(initial_folder)
    else:
        show_header("Updating repository")
        update_success, error_message = update_repo(vedc_repo_folder)
        if not update_success:
            print(
                f"ERROR: Could not update {vedc_repo_folder}: {error_message}"
                f"You might need to delete the folder and try again."
            )
            abort(initial_folder)

    os.chdir(vedc_repo_folder)

    # Get password for sudo stuff
    if not args.yes:
        password = password_prompt()
    else:
        password = None

    # Install Spinnaker SDK
    show_header("Installing Spinnaker SDK")
    install_spinnaker_sdk(
        os.path.join(
            vedc_repo_folder, "installer", "spinnaker_sdk_1.27.0.48_amd64",
        ),
        password,
    )

    # Create udev rules for libuvc
    create_libuvc_udev_rules(password)

    # Install miniconda if necessary
    if not os.path.exists(conda_binary):
        show_header("Installing miniconda")
        install_miniconda(miniconda_prefix)

    # Create or update environment
    if not os.path.exists(os.path.join(miniconda_prefix, "envs", "vedc")):
        show_header("Creating environment")
        # TODO pipe stdout to logger
        subprocess.run([conda_binary, "env", "create"], check=True)
    else:
        show_header("Updating environment")
        # TODO pipe stdout to logger
        subprocess.run([conda_binary, "env", "update"], check=True)

    # Success
    os.chdir(initial_folder)
    print("Installation successful. Congratulations! 🎉🎉🎉")
