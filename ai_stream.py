"""
Simple video frame streamer using OpenCV with WebRTC support
"""

import cv2
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame
from fractions import Fraction

from ai_service import anomaly_detection, process_frame


class VideoFrameStream(VideoStreamTrack):
    """
    Video stream that reads frames from a video URL/file using OpenCV.
    Extends aiortc.VideoStreamTrack for WebRTC streaming.
    """

    kind = "video"

    def __init__(self, video_url: str):
        """
        Initialize the video stream.

        Args:
            video_url (str): URL or path to the video file
        """
        super().__init__()
        self.video_url = video_url
        self.cap: cv2.VideoCapture | None = None
        self._timestamp = 0
        self.anomaly_log = open("./logs/anomaly_log.txt", "a")

    def open(self) -> bool:
        """
        Open the video stream.

        Returns:
            bool: True if opened successfully, False otherwise
        """
        self.cap = cv2.VideoCapture(self.video_url)
        return self.cap.isOpened()

    async def recv(self) -> VideoFrame:
        """
        Receive the next video frame (required by MediaStreamTrack).

        Returns:
            VideoFrame: The next frame as av.VideoFrame for WebRTC streaming
        """
        # Get frame from OpenCV
        if self.cap is None or not self.cap.isOpened():
            self.open()

        if self.cap is None:
            raise Exception("Failed to open video capture")

        ret, frame = self.cap.read()
        if not ret or frame is None:
            # Video ended - stop the track and close connection gracefully
            self.stop()
            raise MediaStreamError

        # person detection
        detections = process_frame(frame)
        border_color = (0, 255, 0)

        # anomaly detection and logging
        is_anomaly = anomaly_detection(detections, frame)
        if is_anomaly:
            border_color = (0, 0, 255)
            self.anomaly_log.write(
                "Anomaly detected at timestamp: {}\n".format(self._timestamp)
            )

        for x, y, w, h in detections:
            x, y, w, h = int(x), int(y), int(w), int(h)
            cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, 2)
        # Ensure frame is uint8 numpy array
        frame_uint8 = np.asarray(frame, dtype=np.uint8)

        # Convert OpenCV frame (BGR numpy array) to av.VideoFrame
        video_frame = VideoFrame.from_ndarray(frame_uint8, format="bgr24")

        # Set timestamp
        video_frame.pts = self._timestamp
        video_frame.time_base = Fraction(1, 90000)

        self._timestamp += 3000  # Increment for ~30fps (90000/30 = 3000)

        return video_frame

    def close(self):
        """
        Close the video stream and release resources.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.anomaly_log.close()
