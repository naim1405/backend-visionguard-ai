import cv2
import numpy as np

# pyright: reportPrivateImportUsage=false
from ultralytics import YOLO
from tensorflow.keras import backend as K
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import load_model


yolo_model = YOLO("./models/yolov8n.pt")


# Process a single frame for person detection (tracking not included)
def process_frame(frame):
    # frame actually a picture
    results = yolo_model(frame)
    detections = []

    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0]
        conf = float(box.conf)
        cls = int(box.cls)

        # class 0 = person in COCO
        if cls == 0 and conf > 0.5:
            detections.append([x1, y1, x2 - x1, y2 - y1])

    return detections


# anomaly detection
def focal_loss(gamma=2.0, alpha=0.25):
    def focal_loss_fixed(y_true, y_pred):
        y_pred = K.clip(y_pred, K.epsilon(), 1 - K.epsilon())  # numerical stability
        cross_entropy = -y_true * K.log(y_pred)
        loss = alpha * K.pow(1 - y_pred, gamma) * cross_entropy
        return K.sum(loss, axis=1)

    return focal_loss_fixed


detection_model = load_model(
    "./models/densenet_focal_epoch2.h5",
    custom_objects={"focal_loss_fixed": focal_loss(gamma=2.0, alpha=0.25)},
)


def anomaly_detection(detections, frame):
    for x, y, w, h in detections:
        x, y, w, h = int(x), int(y), int(w), int(h)
        cropped = frame[y : y + h, x : x + w]
        cropped = cv2.resize(cropped, (64, 64))
        cropped_array = image.img_to_array(cropped)
        cropped_array = np.expand_dims(cropped_array, axis=0)  # Add batch dimension
        cropped_array /= 255.0

        prediction = detection_model.predict(cropped_array)
        prdiction_class = np.argmax(prediction, axis=1)[0]
        if prdiction_class == 7:
            return False
        else:
            return True  # Anomaly detected
    return False  # No anomaly
