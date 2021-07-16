""""""
import numpy as np
from numpy import linalg as LA
import cv2

from pupil_recording_interface.decorators import process
from pupil_recording_interface.process.circle_detector import CircleDetector
from pupil_recording_interface.externals.methods import normalize


@process("circle_detector_vedb")
class CircleDetectorVEDB(CircleDetector):
    """ Detector for circular calibration markers.

    This process detects the circular calibration marker used for calibrating
    the gaze mapper. Attach this process to the world camera stream.
    """

    def __init__(
        self,
        scale=0.5,
        marker_size=(12, 300),
        threshold_window_size=13,
        min_area=500,
        max_area=1000,
        circularity=0.8,
        convexity=0.7,
        inertia=0.4,
        display=True,
        **kwargs,
    ):
        """ Constructor. """
        super().__init__(scale=scale, display=display, **kwargs)

        self.circle_tracker = CircleTrackerVEDB(
            scale=scale,
            marker_size=marker_size,
            threshold_window_size=threshold_window_size,
            min_area=min_area,
            max_area=max_area,
            circularity=circularity,
            convexity=convexity,
            inertia=inertia,
        )


class CircleTrackerVEDB:
    def __init__(
        self,
        wait_interval=30,
        roi_wait_interval=120,
        scale=0.5,
        marker_size=(12, 300),
        threshold_window_size=13,
        min_area=500,
        max_area=1000,
        circularity=0.8,
        convexity=0.7,
        inertia=0.4,
    ):
        self.wait_interval = wait_interval
        self.roi_wait_interval = roi_wait_interval
        self._previous_markers = []
        self._predict_motion = []
        self._wait_count = 0
        self._roi_wait_count = 0
        self._flag_check = False
        self._flag_check_roi = False
        self._world_size = None
        self.scale = scale
        self._marker_size = marker_size
        self.threshold_window_size = threshold_window_size
        self.min_area = min_area
        self.max_area = max_area
        self.circularity = circularity
        self.convexity = convexity
        self.inertia = inertia

    def update(self, img):
        """
        Decide whether to track the marker in the roi or in the whole frame
        Return all detected markers

        :param img: input gray image
        :type img: numpy.ndarray
        :return: all detected markers including the information about their
            ellipses, center positions and their type
        (Ref/Stop)
        :rtype: a list containing dictionary with keys: 'ellipses', 'img_pos',
            'norm_pos', 'marker_type'
        """
        img_size = img.shape[::-1]
        if self._world_size is None:
            self._world_size = img_size
        elif self._world_size != img_size:
            self._previous_markers = []
            self._predict_motion = []
            self._wait_count = 0
            self._roi_wait_count = 0
            self._world_size = img_size

        if self._wait_count <= 0 or self._roi_wait_count <= 0:
            self._flag_check = True
            self._flag_check_roi = False
            self._wait_count = self.wait_interval
            self._roi_wait_count = self.roi_wait_interval

        markers = []
        if self._flag_check:
            markers = self._check_frame(img)
            predict_motion = []
            if len(markers) > 0:
                if len(self._previous_markers) in (0, len(markers)):
                    self._flag_check = True
                    self._roi_wait_count -= 1
                    for i in range(len(self._previous_markers)):
                        predict_motion.append(
                            np.array(markers[i]["img_pos"])
                            - np.array(self._previous_markers[i]["img_pos"])
                        )
            else:
                if self._flag_check_roi:
                    self._flag_check = True
                    self._flag_check_roi = False
                else:
                    self._flag_check = False
                    self._flag_check_roi = False

        self._wait_count -= 1
        self._previous_markers = markers
        return markers

    def _check_frame(self, img):
        """
        Track the markers in the ROIs / in the whole frame

        :param img: input gray image
        :type img: numpy.ndarray
        :return: all detected markers including the information about their
            ellipses, center positions and their type (Ref/Stop)
        :rtype: a list containing dictionary with keys: 'ellipses', 'img_pos',
            'norm_pos', 'marker_type'
        """
        img_size = img.shape[::-1]
        marker_list = []

        # Check whole frame
        if not self._flag_check_roi:
            ellipses_list = self.find_vedb_circle_marker(
                img, self.scale, self._marker_size
            )

            # Save the markers in dictionaries
            for ellipses_ in ellipses_list:
                ellipses = ellipses_["ellipses"]
                img_pos = ellipses[0][0]
                norm_pos = normalize(img_pos, img_size, flip_y=True)
                marker_list.append(
                    {
                        "ellipses": ellipses,
                        "img_pos": img_pos,
                        "norm_pos": norm_pos,
                        "marker_type": ellipses_["marker_type"],
                    }
                )

        # Check roi
        else:
            for i in range(len(self._previous_markers)):
                largest_ellipse = self._previous_markers[i]["ellipses"][-1]

                # Set up the boundary of the roi
                if self._predict_motion:
                    predict_center = (
                        largest_ellipse[0][0] + self._predict_motion[i][0],
                        largest_ellipse[0][1] + self._predict_motion[i][1],
                    )
                    b0 = (
                        predict_center[0]
                        - largest_ellipse[1][1]
                        - abs(self._predict_motion[i][0]) * 2
                    )
                    b1 = (
                        predict_center[0]
                        + largest_ellipse[1][1]
                        + abs(self._predict_motion[i][0]) * 2
                    )
                    b2 = (
                        predict_center[1]
                        - largest_ellipse[1][0]
                        - abs(self._predict_motion[i][1]) * 2
                    )
                    b3 = (
                        predict_center[1]
                        + largest_ellipse[1][0]
                        + abs(self._predict_motion[i][1]) * 2
                    )
                else:
                    predict_center = largest_ellipse[0]
                    b0 = predict_center[0] - largest_ellipse[1][1]
                    b1 = predict_center[0] + largest_ellipse[1][1]
                    b2 = predict_center[1] - largest_ellipse[1][0]
                    b3 = predict_center[1] + largest_ellipse[1][0]

                b0 = 0 if b0 < 0 else int(b0)
                b1 = img_size[0] - 1 if b1 > img_size[0] - 1 else int(b1)
                b2 = 0 if b2 < 0 else int(b2)
                b3 = img_size[1] - 1 if b3 > img_size[1] - 1 else int(b3)
                col_slice = b0, b1
                row_slice = b2, b3

                ellipses_list = self.find_vedb_circle_marker(
                    img[slice(*row_slice), slice(*col_slice)],
                    self.scale,
                    self._marker_size,
                )

                # Track the marker which was detected last frame;
                # To avoid more than one markers are detected in one ROI
                if len(ellipses_list):
                    if len(ellipses_list) == 1:
                        right_ellipses = ellipses_list[0]
                    else:
                        pre_pos = np.array(
                            (
                                self._previous_markers[i]["img_pos"][0] - b0,
                                self._previous_markers[i]["img_pos"][1] - b2,
                            )
                        )
                        temp_dist = [
                            LA.norm(e["ellipses"][0][0] - pre_pos)
                            for e in ellipses_list
                        ]
                        right_ellipses = ellipses_list[
                            temp_dist.index(min(temp_dist))
                        ]
                    ellipses = [
                        ((e[0][0] + b0, e[0][1] + b2), e[1], e[2])
                        for e in right_ellipses["ellipses"]
                    ]
                    img_pos = ellipses[0][0]
                    norm_pos = normalize(img_pos, img_size, flip_y=True)
                    # Save the marker in dictionary
                    marker_list.append(
                        {
                            "ellipses": ellipses,
                            "img_pos": img_pos,
                            "norm_pos": norm_pos,
                            "marker_type": right_ellipses["marker_type"],
                        }
                    )

        return marker_list

    def threshold_frame(self, frame, window_size):
        return cv2.adaptiveThreshold(
            frame,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            window_size,
            2,
        )

    def erode_frame(self, frame, window_size):
        kernel = np.ones((window_size, window_size), int)
        return cv2.erode(frame, kernel, iterations=1)

    def define_blob_detector(self):
        # Todo: Make sure these parameters are passed through constructor
        #  arguments

        # Set our filtering parameters
        # Initialize parameter settiing using cv2.SimpleBlobDetector
        params = cv2.SimpleBlobDetector_Params()

        # Set Area filtering parameters
        params.filterByArea = True
        params.minArea = self.min_area
        params.maxArea = self.max_area

        # Set Circularity filtering parameters
        params.filterByCircularity = True
        params.minCircularity = self.circularity
        # params.minCircularity = 0.7
        # Set Convexity filtering parameters
        params.filterByConvexity = True
        params.minConvexity = self.convexity
        # params.minConvexity = 0.7
        # Set inertia filtering parameters
        params.filterByInertia = True
        params.minInertiaRatio = self.inertia
        # params.minInertiaRatio = 0.6

        # Create a detector with the parameters
        return cv2.SimpleBlobDetector_create(params)

    def find_vedb_circle_marker(self, frame, scale, marker_size):

        # Resize the image
        image = cv2.resize(frame, None, fx=scale, fy=scale)
        ellipses_list = []

        # Here we set up our opencv blob detecter code
        detector = self.define_blob_detector()

        # Perform image thresholding using an adaptive threshold window
        window_size = self.threshold_window_size
        image = self.threshold_frame(image, window_size)

        # Perform image erosion in order to remove the possible bright points
        # inside the marker
        window_size = 3
        image = self.erode_frame(image, window_size)

        # Detect blobs using opencv blob detector that we setup earlier in the
        # code
        keypoints = detector.detect(image)

        # Check if there is any blobs detected or not, if yes then draw it
        # using a red color
        if len(keypoints) > 0:

            for keypoint in keypoints:
                # Todo: Define acceptable range through constructor argument
                if (
                    marker_size[0] < keypoint.size < marker_size[1]
                ):  # 15 and 42
                    # Todo: Make sure the fields in ellipse are the same as in
                    #  pupil code
                    # Todo: Make sure whether the opencv y axis needs to be
                    #  negated!!
                    ellipses_list.append(
                        {
                            "ellipses": [
                                (
                                    (
                                        keypoint.pt[0] * (1 / scale),
                                        keypoint.pt[1] * (1 / scale),
                                    ),
                                    (keypoint.size, keypoint.size),
                                    keypoint.angle,
                                ),
                            ],
                            "marker_type": "Ref",
                        }
                    )
        return ellipses_list
