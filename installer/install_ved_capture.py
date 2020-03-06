""""""
import os
import subprocess
import argparse
import requests
import tempfile


def show_welcome_message(yes=False):
    """"""
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

    if yes:
        return True
    else:
        answer = input(
            "Do you have a GitHub account that is member of the "
            "VEDB organization? [y/n]:"
        )
        print("")
        return answer == "y"


def check_ssh_pubkey(filename="id_ecdsa.pub"):
    """"""
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return f.read()
    else:
        return None


def generate_ssh_keypair(spec="-b 512 -t ecdsa", filename="id_ecdsa"):
    """"""
    filepath = os.path.join(os.path.expanduser("~/.ssh"), filename)

    try:
        subprocess.run(
            "ssh-keygen -q -N \"\" -f ".split() + [filepath] + spec.split(),
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
        subprocess.run(
            ["git", "pull"], check=True, stdout=subprocess.DEVNULL,
        )
        return True, None
    except subprocess.CalledProcessError as e:
        return True, e.output


def install_miniconda(prefix="~/miniconda3"):
    """"""
    prefix = os.path.expanduser(prefix)

    file_handle = requests.get(
        "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    )

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(file_handle.content)
        filename = f.name

        cmd = ["bash", filename, "-b", "-p", prefix]
    subprocess.run(cmd, stdout=subprocess.DEVNULL)


if __name__ == "__main__":

    # Parse command line arguments
    parser = argparse.ArgumentParser("install_ved_capture.py")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="set this flag to install non-interactively"
    )
    parser.add_argument(
        "-f",
        "--folder",
        default="~/vedb",
        help="base folder for installation",
    )
    parser.add_argument(
        "--miniconda_prefix",
        default="~/miniconda3",
        help="prefix for miniconda installation",
    )
    args = parser.parse_args()

    # Config
    base_folder = os.path.expanduser(args.folder)
    vedc_repo_url = "ssh://git@github.com/vedb/ved-capture"
    vedc_repo_folder = get_repo_folder(base_folder, vedc_repo_url)
    miniconda_prefix = os.path.expanduser(args.miniconda_prefix)
    conda_binary = os.path.join(miniconda_prefix, "bin", "conda")

    # Welcome message
    if not show_welcome_message(args.yes):
        print(
            "Please contact someone from the VEDB team to give you access."
        )
        exit(1)

    # Check SSH key
    ssh_key = check_ssh_pubkey()
    if ssh_key is None:
        print("Generating ECDSA key...")
        ssh_key = generate_ssh_keypair()
        show_github_ssh_instructions(ssh_key)
        if args.yes:
            print("When you're done, run this script again.")
            exit(1)
        else:
            input("When you're done, press Enter.")
            print("")

    # Clone or update repository
    if not os.path.exists(vedc_repo_folder):
        clone_success, _ = clone_repo(base_folder, vedc_repo_url)
        if not clone_success:
            print(
                "ERROR: Could not clone the repository. Did you set up the "
                "SSH key?"
            )
            show_github_ssh_instructions(ssh_key)
            exit(1)
    else:
        update_success, error_message = update_repo(vedc_repo_folder)
        if not update_success:
            print(
                f"ERROR: Could not update {vedc_repo_folder}: {error_message}"
                f"You might need to delete the folder and try again."
            )

    # Install miniconda if necessary
    if not os.path.exists(conda_binary):
        install_miniconda(miniconda_prefix)

    # Create environment
    os.chdir(vedc_repo_folder)
    subprocess.run([conda_binary, "env", "create"], check=True)

    # Success
    print("Installation successful. Congratulations!🎉🎉🎉🎉")
