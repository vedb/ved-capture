""""""
import logging

from pupil_recording_interface.decorators import process
from pupil_recording_interface.process.calibration import Calibration
import numpy as np

logger = logging.getLogger(__name__)


# TODO once pri 1.0 is released:
#  @process("validation", optional=("resolution",))
class Validation(Calibration):
    """ Validation during runtime class. """

    def __init__(
        self,
        resolution,
        eye_resolution=None,
        mode="2d",
        min_confidence=0.8,
        left="eye1",
        right="eye0",
        world="world",
        name=None,
        folder=None,
        save=False,
        **kwargs,
    ):
        """ Constructor. """
        super().__init__(
            resolution,
            mode=mode,
            min_confidence=min_confidence,
            left=left,
            right=right,
            world=world,
            name=name,
            folder=folder,
            save=save,
            **kwargs,
        )
        self.eye_resolution = eye_resolution

    def plot_markers(self, circle_marker_list, filename):
        """ Plot marker coverage. """
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 8))
        x = [c["img_pos"][0] for c in circle_marker_list]
        y = [c["img_pos"][1] for c in circle_marker_list]
        # Note that: y axis in opencv is inverse of matplotlib!
        logger.debug(f"plotting {len(x)} marker points")
        plt.plot(
            x, self.resolution[1] - np.array(y), "or", markersize=10, alpha=0.7
        )
        plt.xlim(0, self.resolution[0])
        plt.ylim(0, self.resolution[1])
        plt.grid(True)
        plt.title("Marker Position", fontsize=18)
        plt.rc("xtick", labelsize=12)
        plt.rc("ytick", labelsize=12)
        plt.xlabel("X (pixels)", fontsize=14)
        plt.ylabel("Y (pixels)", fontsize=14)
        # Todo: Check if we can pass a flag to show the plots
        #  (currently doesn't work with the thread timers)
        # plt.show()
        if filename is not None:
            figure_file_name = filename.parent / "marker_coverage.png"
            plt.savefig(figure_file_name, dpi=200)
            logger.info(f"saved marker plot at: {figure_file_name}")
        plt.close()

    def plot_pupils(self, pupil_list, filename):
        """ Plot pupil coverage. """
        import matplotlib.pyplot as plt

        if self.eye_resolution is None:
            res = (1.0, 1.0)
        else:
            res = self.eye_resolution
        plt.figure(figsize=(8, 8))
        x = [p["norm_pos"][0] * res[0] for p in pupil_list if p["id"] == 0]
        y = [p["norm_pos"][1] * res[1] for p in pupil_list if p["id"] == 0]
        logger.debug(f"plotting {len(x)} right pupil points")
        plt.plot(x, y, "*y", markersize=10, alpha=0.7, label="right")

        x = [p["norm_pos"][0] * res[0] for p in pupil_list if p["id"] == 1]
        y = [p["norm_pos"][1] * res[1] for p in pupil_list if p["id"] == 1]
        logger.debug(f"plotting {len(x)} left pupil points")
        plt.plot(x, y, "*g", markersize=10, alpha=0.7, label="left")

        plt.xlim(0, res[0])
        plt.ylim(0, res[1])
        plt.grid(True)
        plt.title("Pupil Position", fontsize=18)
        plt.rc("xtick", labelsize=12)
        plt.rc("ytick", labelsize=12)
        if self.eye_resolution is not None:
            plt.xlabel("X (pixels)", fontsize=14)
            plt.ylabel("Y (pixels)", fontsize=14)
        else:
            plt.xlabel("X (normalized position)", fontsize=14)
            plt.ylabel("Y (normalized position)", fontsize=14)
        if filename is not None:
            figure_file_name = filename.parent / "pupil_coverage.png"
            plt.savefig(figure_file_name, dpi=200)
            logger.info(f"saved pupil plot at: {figure_file_name}")
        # Todo: Check if we can pass a flag to show the plots
        #  (currently doesn't work with the thread timers)
        # plt.show()
        plt.close()

    def calculate_calibration(self):
        """ Calculate calibration from collected data. """
        (
            circle_marker_list,
            pupil_list,
            filename,
        ) = super().calculate_calibration()
        logger.info("Plotting Coverage for marker and pupil...")
        self.plot_markers(circle_marker_list, filename)
        self.plot_pupils(pupil_list, filename)

        logger.info("Validation and Calibration Done Successfully!")
        return circle_marker_list, pupil_list, filename
