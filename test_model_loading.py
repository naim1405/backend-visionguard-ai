"""
Model Loading Test for STG-NF Integration
Tests that all models load correctly on the configured device
"""

import sys
import torch
import cv2
import numpy as np

print("=" * 70)
print("STG-NF Model Loading Test")
print("=" * 70)

# Test 1: Check CUDA availability
print("\n[Test 1] Checking CUDA availability...")
if torch.cuda.is_available():
    print(f"✓ CUDA is available")
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  CUDA Version: {torch.version.cuda}")
    print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    device = "cuda:0"
else:
    print("⚠ CUDA not available, using CPU")
    device = "cpu"

# Test 2: Load configuration
print("\n[Test 2] Loading configuration...")
try:
    from config import (
        YOLO_MODEL_PATH,
        POSE_MODEL_PATH,
        ANOMALY_MODEL_PATH,
        ANOMALY_THRESHOLD,
        DEVICE,
        SEQUENCE_LENGTH
    )
    print(f"✓ Configuration loaded successfully")
    print(f"  YOLO Model: {YOLO_MODEL_PATH}")
    print(f"  Pose Model: {POSE_MODEL_PATH}")
    print(f"  Anomaly Model: {ANOMALY_MODEL_PATH}")
    print(f"  Device: {DEVICE}")
    print(f"  Sequence Length: {SEQUENCE_LENGTH}")
    print(f"  Anomaly Threshold: {ANOMALY_THRESHOLD}")
except Exception as e:
    print(f"✗ Failed to load configuration: {e}")
    sys.exit(1)

# Test 3: Load Person Detector
print("\n[Test 3] Loading Person Detector (YOLOv8)...")
try:
    from detection.person_detector import PersonDetector
    detector = PersonDetector(YOLO_MODEL_PATH, device=DEVICE)
    print(f"✓ Person Detector loaded successfully")
    print(f"  Model: {YOLO_MODEL_PATH}")
    print(f"  Device: {DEVICE}")
except Exception as e:
    print(f"✗ Failed to load Person Detector: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Load Tracker
print("\n[Test 4] Loading Tracker (Deep SORT)...")
try:
    from detection.tracker import PersonTracker
    tracker = PersonTracker()
    print(f"✓ Tracker loaded successfully")
except Exception as e:
    print(f"✗ Failed to load Tracker: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Load Frame Buffer Manager
print("\n[Test 5] Loading Frame Buffer Manager (YOLOv8-Pose)...")
try:
    from detection.frame_buffer import FrameBufferManager
    frame_buffer = FrameBufferManager(
        pose_model_path=POSE_MODEL_PATH,
        sequence_length=SEQUENCE_LENGTH,
        device=DEVICE
    )
    print(f"✓ Frame Buffer Manager loaded successfully")
    print(f"  Pose Model: {POSE_MODEL_PATH}")
    print(f"  Sequence Length: {SEQUENCE_LENGTH}")
except Exception as e:
    print(f"✗ Failed to load Frame Buffer Manager: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Load Anomaly Detector
print("\n[Test 6] Loading Anomaly Detector (STG-NF)...")
try:
    from detection.anomaly_detector import AnomalyDetector
    anomaly_detector = AnomalyDetector(
        checkpoint_path=ANOMALY_MODEL_PATH,
        threshold=ANOMALY_THRESHOLD,
        device=DEVICE
    )
    print(f"✓ Anomaly Detector loaded successfully")
    print(f"  Checkpoint: {ANOMALY_MODEL_PATH}")
    print(f"  Threshold: {ANOMALY_THRESHOLD}")
except Exception as e:
    print(f"✗ Failed to load Anomaly Detector: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Check GPU Memory Usage
if torch.cuda.is_available():
    print("\n[Test 7] Checking GPU Memory Usage...")
    allocated = torch.cuda.memory_allocated(0) / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    print(f"✓ GPU Memory Status:")
    print(f"  Allocated: {allocated:.2f} GB")
    print(f"  Reserved: {reserved:.2f} GB")
    print(f"  Free: {torch.cuda.get_device_properties(0).total_memory / 1024**3 - reserved:.2f} GB")

# Test 8: Quick inference test
print("\n[Test 8] Running quick inference test...")
try:
    # Create a dummy frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Test detection
    detections = detector.detect(test_frame)
    print(f"✓ Detection test passed (found {len(detections)} persons)")
    
    # Test tracking (if detections found)
    if len(detections) > 0:
        tracking_data = tracker.update(detections, test_frame)
        print(f"✓ Tracking test passed (tracking {len(tracking_data)} persons)")
    else:
        print(f"⚠ No persons detected in test frame (expected for blank frame)")
    
except Exception as e:
    print(f"✗ Inference test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("✓ ALL TESTS PASSED!")
print("=" * 70)
print("\nSTG-NF Integration Status:")
print("  ✓ All models loaded successfully")
print("  ✓ GPU/CPU configuration correct")
print("  ✓ Pipeline components functional")
print("  ✓ Ready for WebRTC streaming")
print("\nNext Steps:")
print("  1. Start the backend: python main.py")
print("  2. Connect with WebRTC frontend")
print("  3. Test with real video streams")
print("=" * 70)
