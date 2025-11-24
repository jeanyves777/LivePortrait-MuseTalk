#!/usr/bin/env python3
"""
LivePortrait RunPod Serverless Handler
Facial animation with expression control using motion templates
https://github.com/KwaiVGI/LivePortrait
"""

import runpod
import os
import sys
import torch
import tempfile
import shutil
import requests
import traceback
from pathlib import Path
from dataclasses import dataclass

print("[LivePortrait] Starting handler...")

# Add LivePortrait to path
sys.path.insert(0, '/workspace/LivePortrait')

from src.config.inference_config import InferenceConfig
from src.config.crop_config import CropConfig
from src.live_portrait_pipeline import LivePortraitPipeline

# S3 Configuration
S3_ACCESS_KEY = os.environ.get('RUNPOD_S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('RUNPOD_S3_SECRET_KEY')
S3_BUCKET = os.environ.get('RUNPOD_S3_BUCKET', 'flowsmartly-avatars')
S3_ENDPOINT = os.environ.get('RUNPOD_S3_ENDPOINT', 'https://storage.runpod.io')

# Import S3 client if credentials available
s3_client = None
if S3_ACCESS_KEY and S3_SECRET_KEY:
    try:
        import boto3
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY
        )
        print("[S3] ✅ S3 client initialized")
    except Exception as e:
        print(f"[S3] ⚠️ S3 client failed: {e}")

# Global model (loaded once)
live_portrait_pipeline = None

# Built-in expression templates from LivePortrait
EXPRESSION_TEMPLATES = {
    'neutral': '/workspace/LivePortrait/assets/examples/driving/d0.mp4',  # Default neutral
    'smile': '/workspace/LivePortrait/assets/examples/driving/laugh.pkl',
    'sad': '/workspace/LivePortrait/assets/examples/driving/aggrieved.pkl',
    'surprised': '/workspace/LivePortrait/assets/examples/driving/d5.pkl',
    'approve': '/workspace/LivePortrait/assets/examples/driving/d1.pkl',  # Nodding
    'disapprove': '/workspace/LivePortrait/assets/examples/driving/shake_face.pkl',
    'confused': '/workspace/LivePortrait/assets/examples/driving/shy.pkl',
    'wink': '/workspace/LivePortrait/assets/examples/driving/wink.pkl',
    'talking': '/workspace/LivePortrait/assets/examples/driving/talking.pkl',
}

@dataclass
class SimpleArgs:
    """Simplified arguments for LivePortrait execution"""
    source: str
    driving: str
    output_dir: str = '/tmp/output'
    flag_use_half_precision: bool = True
    flag_crop_driving_video: bool = False
    device_id: int = 0
    flag_force_cpu: bool = False
    flag_normalize_lip: bool = False
    flag_source_video_eye_retargeting: bool = False
    flag_eye_retargeting: bool = False
    flag_lip_retargeting: bool = False
    flag_stitching: bool = True
    flag_relative_motion: bool = True
    flag_pasteback: bool = True
    flag_do_crop: bool = True
    driving_option: str = "expression-friendly"
    driving_multiplier: float = 1.0
    driving_smooth_observation_variance: float = 3e-7
    audio_priority: str = 'driving'
    animation_region: str = "all"
    det_thresh: float = 0.15
    scale: float = 2.3
    vx_ratio: float = 0
    vy_ratio: float = -0.125
    flag_do_rot: bool = True
    source_max_dim: int = 1280
    source_division: int = 2
    scale_crop_driving_video: float = 2.2
    vx_ratio_crop_driving_video: float = 0.0
    vy_ratio_crop_driving_video: float = -0.1

def initialize_liveportrait():
    """Initialize LivePortrait pipeline"""
    global live_portrait_pipeline

    try:
        print("[LivePortrait] Loading models...")

        # Initialize configuration
        inference_cfg = InferenceConfig()
        crop_cfg = CropConfig()

        # Initialize pipeline
        live_portrait_pipeline = LivePortraitPipeline(
            inference_cfg=inference_cfg,
            crop_cfg=crop_cfg
        )

        print("[LivePortrait] ✅ Pipeline loaded successfully")
        return True

    except Exception as e:
        print(f"[LivePortrait] ❌ Failed to load: {e}")
        traceback.print_exc()
        return False

def download_file(url, local_path):
    """Download file from URL"""
    try:
        print(f"[Download] {url}")
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[Download] ✅ Saved to {local_path}")
        return local_path, None

    except Exception as e:
        error = f"Download failed: {str(e)}"
        print(f"[Download] ❌ {error}")
        return None, error

def upload_to_s3(local_path, object_name=None):
    """Upload file to S3"""
    if not s3_client:
        return None, "S3 not configured"

    try:
        if object_name is None:
            object_name = f"liveportrait-output/{Path(local_path).name}"

        print(f"[S3] Uploading to {S3_BUCKET}/{object_name}")

        s3_client.upload_file(
            local_path,
            S3_BUCKET,
            object_name,
            ExtraArgs={'ACL': 'public-read'}
        )

        url = f"{S3_ENDPOINT}/{S3_BUCKET}/{object_name}"
        print(f"[S3] ✅ Uploaded: {url}")
        return url, None

    except Exception as e:
        error = f"S3 upload failed: {str(e)}"
        print(f"[S3] ❌ {error}")
        return None, error

def generate_animation(
    source_image_path,
    expression='neutral',
    output_dir=None
):
    """
    Generate facial animation using LivePortrait

    Args:
        source_image_path: Path to source portrait image
        expression: Expression name (neutral, smile, sad, etc.)
        output_dir: Directory to save output

    Returns:
        (video_path, motion_template_path, error)
    """
    try:
        if not live_portrait_pipeline:
            if not initialize_liveportrait():
                return None, None, "LivePortrait pipeline not available"

        print(f"[LivePortrait] Generating animation: expression={expression}")

        # Get expression template
        driving_template = EXPRESSION_TEMPLATES.get(expression.lower(), EXPRESSION_TEMPLATES['neutral'])

        if not os.path.exists(driving_template):
            return None, None, f"Expression template not found: {driving_template}"

        # Create output directory
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        os.makedirs(output_dir, exist_ok=True)

        # Prepare arguments
        args = SimpleArgs(
            source=source_image_path,
            driving=driving_template,
            output_dir=output_dir,
        )

        # Generate animation
        print(f"[LivePortrait] Running pipeline...")
        live_portrait_pipeline.execute(args)

        # Find output file
        output_files = list(Path(output_dir).glob("*.mp4"))
        if not output_files:
            return None, None, "No output video generated"

        output_video = str(output_files[0])
        print(f"[LivePortrait] ✅ Video generated: {output_video}")

        # Note: Motion template saving would need to be added to LivePortrait pipeline
        # For now, we'll just return the video
        return output_video, None, None

    except Exception as e:
        error = f"Animation generation failed: {str(e)}"
        print(f"[LivePortrait] ❌ {error}")
        traceback.print_exc()
        return None, None, error

def handler(job):
    """
    RunPod serverless handler

    Expected input:
    {
        "source_image_url": "https://example.com/portrait.jpg",
        "expression": "smile"  // optional, default: "neutral"
    }
    """
    job_input = job.get('input', {})

    # Get inputs
    source_image_url = job_input.get('source_image_url')
    expression = job_input.get('expression', 'neutral')

    if not source_image_url:
        return {"error": "source_image_url is required"}

    print(f"\n[Job] Starting LivePortrait animation")
    print(f"[Job] Source image: {source_image_url}")
    print(f"[Job] Expression: {expression}")

    # Create temp directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Download source image
        source_image_path = os.path.join(temp_dir, 'source.jpg')
        source_image_path, error = download_file(source_image_url, source_image_path)
        if error:
            return {"error": f"Failed to download source image: {error}"}

        # Generate animation
        output_dir = os.path.join(temp_dir, 'output')
        video_path, template_path, error = generate_animation(
            source_image_path=source_image_path,
            expression=expression,
            output_dir=output_dir
        )

        if error:
            return {"error": error}

        # Upload results to S3
        video_url = None
        template_url = None

        if video_path and os.path.exists(video_path):
            video_url, error = upload_to_s3(video_path)
            if error:
                print(f"[Job] ⚠️ Video upload failed: {error}")
                video_url = video_path  # Return local path

        if template_path and os.path.exists(template_path):
            template_url, error = upload_to_s3(template_path)
            if error:
                print(f"[Job] ⚠️ Template upload failed: {error}")

        # Clean up
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

        print(f"[Job] ✅ Complete!")

        return {
            "video_url": video_url,
            "motion_template_url": template_url,
            "expression": expression,
            "status": "completed"
        }

    except Exception as e:
        # Clean up
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

        error_msg = f"Handler error: {str(e)}"
        print(f"[Job] ❌ {error_msg}")
        traceback.print_exc()

        return {"error": error_msg}

# Initialize models at startup
print("[LivePortrait] Pre-loading pipeline...")
initialize_liveportrait()
print("[LivePortrait] Handler ready!")

# Start RunPod handler
if __name__ == "__main__":
    print("[RunPod] Starting serverless handler...")
    runpod.serverless.start({"handler": handler})
