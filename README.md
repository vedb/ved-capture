[![Build status](https://github.com/vedb/ved-capture/workflows/build/badge.svg)](https://github.com/vedb/ved-capture/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# ved-capture

**ved-capture** is the app for simultaneous recording of video, gaze and head
tracking data for the Visual Experience Database.
 
## Installation

The app can be installed on most Linux systems with a single Python script that
can be downloaded [here](https://github.com/vedb/ved-capture/blob/master/installer/install_ved_capture.py) 
by right clicking on the "Raw" button and then "Save target as" 
or on the [Releases page](https://github.com/vedb/ved-capture/releases). 

    $ python3 install_ved_capture.py
    
The script will guide you through the setup process and instruct you what to 
do. Since the app isolates all of it's dependencies in a dedicated
environment, the installation has a size of about 2 GB, so make sure you 
have enough space.
 
## Usage

The central tool of this app is the command line tool `vedc`. You can use it
 to generate recording configurations, make recordings and update the app.
 
### Generating a configuration

Plug in your hardware (Pupil core system, RealSense T265, FLIR camera) and run:

    $ vedc generate_config
    
This will check your connected devices and ask you several questions. At
the end it will create a config file `~/.config/vedc/config.yaml` that will
work for your current setup.

### Streaming video

To show one or more configured video streams, run:

    $ vedc show <stream1> <stream2> ...


### Recording

For recording the configured streams, run:

    $ vedc record

By default, the data is recorded to `~/recordings/<today>/<no>`. After 
recording, the data can be loaded into Pupil Player for inspection.
 

### Calibration

The gaze mapper can be calibrated with:

    $ vedc calibrate
    

### Estimating camera parameters

Camera intrinsics can be estimated with:

    $ vedc estimate_cam_params <stream>
    
where `<stream>` is the name of one of the streams you've set up, e.g. `world`.

  
### Updating

To update the app, run:
 
    $ vedc update


### Getting help

Contact one of the developers (Peter or Kamran) for assistance. You can export
the application logs with:

    $ vedc save_logs
