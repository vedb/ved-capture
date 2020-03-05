""""""
import os
import subprocess


def show_welcome_message():
    """"""
    print(
        "###################################################\n"
        "# Welcome to the VED capture installation script. #\n"
        "###################################################\n\n"
        "This script will guide you through the setup process for VED "
        "capture.\n"
    )


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
        f"When you're done, run this script again."
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
        return True, get_repo_folder(repo_url)
    except subprocess.CalledProcessError as e:
        return False, e.output


if __name__ == '__main__':

    # Config
    base_folder = os.path.expanduser("~/vedb")
    vedc_repo_url = "ssh://git@github.com/vedb/ved-capture"
    vedc_repo_folder = get_repo_folder(base_folder, vedc_repo_url)

    # Welcome message
    show_welcome_message()

    # Check SSH key
    ssh_key = check_ssh_pubkey()
    if ssh_key is None:
        print("No ECDSA key found, generating...")
        ssh_key = generate_ssh_keypair()
        show_github_ssh_instructions(ssh_key)
        exit(1)

    if not os.path.exists(vedc_repo_folder):

        # Try to clone git repo
        clone_success, _ = clone_repo(base_folder, vedc_repo_url)
        if not clone_success:
            print("ERROR: Could not clone the repository. "
                  "Did you set up the SSH key?")
            show_github_ssh_instructions(ssh_key)
            exit(1)

    # Install dependencies
    os.chdir(vedc_repo_folder)
    # TODO

    # Success
    print("Installation successful. Congratulations!🎉🎉🎉🎉")
