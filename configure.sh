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
sudo update-grup
