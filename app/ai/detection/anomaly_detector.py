"""
Anomaly Detector Module
Adapted from vis-new/inference_only/json_inference.py
Uses STG-NF model for pose-based anomaly detection
"""

import numpy as np
import torch
from .utils import gen_clip_seg_data_np, normalize_pose

# Import STG-NF model - will be available after copying model architecture
import sys
import os
# Add models directory to path for STG_NF imports
models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'models'))
sys.path.insert(0, models_path)

from STG_NF.model_pose import STG_NF


class AnomalyDetector:
    """
    STG-NF based anomaly detector for pose sequences
    """
    
    def __init__(self, checkpoint_path: str, threshold: float = 0.0, device: str = "cuda:0"):
        """
        Initialize anomaly detector
        
        Args:
            checkpoint_path: Path to trained STG-NF .pth model
            threshold: Anomaly threshold (from training EER)
            device: 'cuda:0', 'cpu', or None (auto-detect)
        """
        if device is None:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.threshold = threshold

        # Load checkpoint
        print(f"Loading STG-NF model from: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=self.device)

        # Model configuration (must match training args.json)
        model_config = {
            "pose_shape": (2, 24, 18),  # seg_len=24
            "hidden_channels": 0,  # model_hidden_dim=0 → single block architecture
            "K": 8,
            "L": 1,
            "actnorm_scale": 1.0,
            "flow_permutation": "permute",
            "flow_coupling": "affine",
            "LU_decomposed": True,
            "learn_top": False,
            "R": 3.0,
            "edge_importance": False,
            "temporal_kernel_size": None,  # Auto: T//2+1 = 13
            "strategy": "uniform",
            "max_hops": 8,
            "device": self.device,
        }

        # Create and load model
        self.model = STG_NF(**model_config)
        self.model.load_state_dict(checkpoint["state_dict"])
        
        # Mark all ActNorm layers as initialized (required after loading checkpoint)
        for module in self.model.modules():
            if hasattr(module, 'inited'):
                module.inited = True
        
        self.model.to(self.device)
        self.model.eval()

        print(f"✓ STG-NF model loaded (trained for {checkpoint['epoch']} epochs)")
        print(f"✓ Using device: {self.device}")

    def predict(self, clip_dict, scene_id="live", clip_id="stream"):
        """
        Run anomaly detection on pose data
        
        Args:
            clip_dict: Python dict with pose tracking data
                Format: {person_id: {frame_num: {"keypoints": [51 values], "score": float}}}
            scene_id: Scene identifier (default: 'live')
            clip_id: Clip identifier (default: 'stream')
            
        Returns:
            results: List of detection results for each person/sequence
                Format: [{person_id, score, is_abnormal, classification, confidence, ...}]
        """
        # Process JSON to get pose segments
        segs_data_np, segs_meta, person_keys, _, _, segs_score_np = (
            gen_clip_seg_data_np(
                clip_dict,
                start_ofst=0,
                seg_stride=6,  # Stride=6 to match training
                seg_len=24,  # Model trained with 24 frames
                scene_id=scene_id,
                clip_id=clip_id,
                ret_keys=True,
                dataset="PoseLift",
            )
        )

        if segs_data_np.shape[0] == 0:
            print("⚠️  No valid segments generated from pose data")
            return []

        print(f"📊 Generated {segs_data_np.shape[0]} segments, shape: {segs_data_np.shape}")

        # Normalize poses (input: [N, T, V, F], output: same shape)
        # segs_data_np is [N, 24, 17, 3] from gen_clip_seg_data_np
        segs_data_np = normalize_pose(
            segs_data_np, scale=True, scale_proportional=True
        )

        # Check for NaN after normalization
        if np.isnan(segs_data_np).any():
            print("⚠️  NaN detected after normalization!")
            print(f"   NaN count: {np.isnan(segs_data_np).sum()}")
            # Replace NaN with zeros
            segs_data_np = np.nan_to_num(segs_data_np, nan=0.0)

        # Convert to model input format [N, 2, 24, 18]
        # Currently: [N, 24, 17, 3] (batch, frames, keypoints, x/y/conf)
        # Need: [N, 2, 24, 18] (batch, x/y, frames, keypoints+1)

        poses = segs_data_np[:, :, :, :2]  # Remove confidence, keep only x,y → [N, 24, 17, 2]
        poses = np.transpose(poses, (0, 3, 1, 2))  # [N, 2, 24, 17]
        
        # Pad from 17 to 18 keypoints (COCO17 → COCO18)
        poses = np.pad(poses, ((0, 0), (0, 0), (0, 0), (0, 1)), mode='constant')  # [N, 2, 24, 18]

        print(f"🔄 Model input shape: {poses.shape}")

        # Run inference
        poses_tensor = torch.from_numpy(poses).float().to(self.device)

        with torch.no_grad():
            _, nll = self.model(
                poses_tensor,
                label=torch.ones(poses_tensor.shape[0]).to(self.device),
                score=torch.ones(poses_tensor.shape[0]).to(self.device),
            )
            scores = -nll.cpu().numpy()

        # Check for NaN in scores
        if np.isnan(scores).any():
            print("⚠️  NaN detected in model output scores!")
            print(f"   Scores: {scores}")
            # Replace NaN with a default value (threshold)
            scores = np.nan_to_num(scores, nan=self.threshold)

        # Compile results
        results = []
        for i, (score, meta) in enumerate(zip(scores, segs_meta)):
            scene, clip, person_id, start_frame = meta
            is_abnormal = score < self.threshold

            # Calculate confidence
            distance = abs(score - self.threshold)
            if distance < -3.0:
                confidence = "High"
            elif distance < -2.0 and distance > -2.9:
                confidence = "Medium"
            else:
                confidence = "Low"

            result = {
                "sequence_id": i,
                "person_id": int(person_id),
                "start_frame": int(start_frame),
                "end_frame": int(start_frame) + 11,
                "score": float(score),
                "is_abnormal": bool(is_abnormal),
                "classification": "Abnormal" if is_abnormal else "Normal",
                "confidence": confidence,
                "scene_id": scene,
                "clip_id": clip,
            }

            results.append(result)

        return results
