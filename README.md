# ved-capture

**ved-capture** is the app for simultaneous recording of camera, gaze and head
 tracking data for the Visual Experience Database.
 
## Installation

The app can be installed on ubuntu 18.04 with a single Python script. 

    $ python3 install_ved_capture.py
    
The script will guide you through the setup process and instruct you what to 
 do. Since the app isolates most of it's dependencies in a dedicated
 environment, the installation has a size of about 3.6 GB, so make sure you 
 have enough space.
 
## Usage

The central tool of this app is the command line tool `vedc`. You can use it
 to generate recording configurations, make recordings and update the app.
 
### Generating a configuration

Plug in your hardware (Pupil core system, RealSense T265, FLIR camera) and run:

    $ vedc generate_config
    
This will check your connected devices and ask you several question. At
 the end it will create a config file `~/.config/vedc/config.yaml` that will
 work for your current setup.

### Recording

Once you have generated a configuration, run:

    $ vedc record
    
to start recording. 

By default, the data is recorded to `~/recordings/<today>/<no>`. After 
 recording, the data can be loaded into Pupil Player for inspection.
  
### Updating

If an update is available, the `vedc record` command will tell you to update. 
 To do this, run:
 
    $ vedc update
