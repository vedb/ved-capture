[![Build status](https://github.com/vedb/ved-capture/workflows/build/badge.svg)](https://github.com/vedb/ved-capture/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# ved-capture

**ved-capture** is the app for simultaneous recording of video, gaze and head
tracking data for the Visual Experience Database.
 
## Installation

Clone the repository:

    $ git clone ssh://git@github.com:vedb/ved-capture
    $ cd ved-capture

Set up the environment:

    $ conda env create

Configure system:

    $ bash configure.sh

Create alias (replace `~/.bashrc` with `~/.zshrc` if using `zsh` as shell):

    $ echo 'alias vedc="conda run -n vedc vedc"' >> ~/.bashrc 
    $ source ~/.bashrc
 
## Usage

The central tool of this app is the command line tool `vedc`. You can use it
to generate recording configurations, make recordings, update the app and more.
 
### Generating a configuration

Plug in your hardware (Pupil core system, RealSense T265, FLIR camera) and run:

    $ vedc auto_config
    
This will check your connected devices and auto-generate a configuration for 
your current setup.

### Streaming video

To show all camera streams, run:

    $ vedc show world eye0 eye1 t265

### Other commands

Check out the [wiki](https://github.com/vedb/ved-capture/wiki) for a 
comprehensive list of available commands.
