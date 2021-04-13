import inspect

import click

from ved_capture.cli.utils import init_logger, raise_error
from ved_capture.utils import (
    get_pupil_devices,
    get_realsense_devices,
    get_flir_devices,
)


@click.command("device_info")
@click.option(
    "-v", "--verbose", default=False, help="Verbose output.", count=True,
)
def device_info(verbose):
    """ Print information about connected devices. """
    logger = init_logger(inspect.stack()[0][3], verbosity=verbose)

    # get connected devices
    pupil_devices = get_pupil_devices()
    t265_devices = get_realsense_devices()
    flir_devices = get_flir_devices()

    # print device info
    if len(pupil_devices):
        logger.info("Connected Pupil Core devices:")
        for device_uid in pupil_devices:
            logger.info(f"* {device_uid}")

    if len(t265_devices):
        logger.info("Connected RealSense T265 devices:")
        for device_uid in t265_devices:
            logger.info(f"* {device_uid}")

    if len(flir_devices):
        logger.info("Connected FLIR devices:")
        for device_uid in flir_devices:
            logger.info(f"* {device_uid}")

    # raise an error if no devices found
    if len(pupil_devices) + len(flir_devices) + len(t265_devices) == 0:
        raise_error("No devices connected!", logger)
