#!/bin/bash

# configure Pupil udev rules
sudo usermod -a -G plugdev $USER
echo 'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", GROUP="plugdev", MODE="0664"' | sudo tee /etc/udev/rules.d/10-libuvc.rules > /dev/null
sudo udevadm trigger

# configure Spinnaker udev rules
sudo groupadd -f flirimaging
sudo usermod -a -G flirimaging $USER
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1e10", GROUP="flirimaging"' | sudo tee /etc/udev/rules.d/40-flir-spinnaker.rules > /dev/null
sudo /etc/init.d/udev restart

# increase USBFS memory
sudo sed -i s/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=1000"/ /etc/default/grub
sudo update-grub

# remove old vedc executable
sudo rm -f /usr/local/bin/vedc

# create alias
CLI_CMD="vedc-cli () { conda activate vedc;  vedc \$@; conda deactivate }"
ALIAS_CMD="alias vedc=vedc-cli"

if [[ "$SHELL" == *bash ]] ; then
  RC_FILE="$HOME/.bashrc"
elif [[ "$SHELL" == *zsh ]] ; then
  RC_FILE="$HOME/.zshrc"
else
  echo "Could not determine shell type, add the following commands to your shell's rc file manually:"
  echo "${CLI_CMD}"
  echo "${ALIAS_CMD}"
  exit 1
fi

if ! grep -Fxq "${CLI_CMD}" "${RC_FILE}"; then
  echo "${CLI_CMD}" >> "${RC_FILE}"
fi

if ! grep -Fxq "${ALIAS_CMD}" "${RC_FILE}"; then
  echo "${ALIAS_CMD}" >> "${RC_FILE}"
fi
