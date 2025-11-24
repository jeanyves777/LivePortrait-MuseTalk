#!/usr/bin/env python3
"""
LivePortrait RunPod Serverless Handler
Facial animation with expression control + motion template generation
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
import pickle
from pathlib import Path

print("[LivePortrait] Starting handler...")

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

# Expression presets (0-6)
EXPRESSIONS = {
    'neutral': 0,
    'approve': 1,
    'disapprove': 2,
    'smile': 3,
    'sad': 4,
    'surprised': 5,
    'confused': 6,
}

def initialize_liveportrait():
    """Initialize LivePortrait pipeline"""
    global live_portrait_pipeline

    try:
        print("[LivePortrait] Loading models...")

        # Add LivePortrait to path
        sys.path.insert(0, '/workspace/LivePortrait')

        from src.config.inference_config import InferenceConfig
        from src.live_portrait_pipeline import LivePortraitPipeline

        # Initialize configuration
        cfg = InferenceConfig()

        # Set device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[LivePortrait] Using device: {device}")

        # Initialize pipeline
        live_portrait_pipeline = LivePortraitPipeline(
            inference_cfg=cfg,
            device=device
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
    driving_video_path=None,
    expression='neutral',
    output_video_path=None,
    output_motion_template_path=None
):
    """
    Generate facial animation using LivePortrait

    Args:
        source_image_path: Path to source portrait image
        driving_video_path: Optional path to driving video (if None, uses expression preset)
        expression: Expression name (neutral, smile, sad, etc.)
        output_video_path: Path to save output video
        output_motion_template_path: Path to save motion template (.pkl)

    Returns:
        (video_path, motion_template_path, error)
    """
    try:
        if not initialize_liveportrait():
            return None, None, "LivePortrait pipeline not available"

        print(f"[LivePortrait] Generating animation: expression={expression}")

        # Prepare arguments
        args = {
            'source_image': source_image_path,
            'flag_relative_motion': True,
            'flag_do_crop': True,
            'flag_pasteback': True,
        }

        # Use driving video if provided, otherwise use expression preset
        if driving_video_path and os.path.exists(driving_video_path):
            args['driving_video'] = driving_video_path
            print(f"[LivePortrait] Using driving video: {driving_video_path}")
        else:
            # Use built-in expression template
            expression_idx = EXPRESSIONS.get(expression, 0)
            args['expression_index'] = expression_idx
            print(f"[LivePortrait] Using expression preset: {expression} (index {expression_idx})")

        # Generate animation
        result = live_portrait_pipeline.execute(args)

        # Save output video
        if output_video_path and 'video' in result:
            import cv2
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(
                output_video_path,
                fourcc,
                result.get('fps', 25.0),
                (result['video'][0].shape[1], result['video'][0].shape[0])
            )
            for frame in result['video']:
                out.write(frame)
            out.release()
            print(f"[LivePortrait] ✅ Video saved: {output_video_path}")

        # Save motion template
        if output_motion_template_path and 'motion_template' in result:
            with open(output_motion_template_path, 'wb') as f:
                pickle.dump(result['motion_template'], f)
            print(f"[LivePortrait] ✅ Motion template saved: {output_motion_template_path}")

        return output_video_path, output_motion_template_path, None

    except Exception as e:
        error = f"Animation generation failed: {str(e)}"
        print(f"[LivePortrait] ❌ {error}")
        traceback.print_exc()
        return None, None, error

def handler(job):
    """
    RunPod serverless handler
    """
    job_input = job.get('input', {})

    # Get inputs
    source_image_url = job_input.get('source_image_url')
    driving_video_url = job_input.get('driving_video_url')  # Optional
    expression = job_input.get('expression', 'neutral')
    generate_motion_template = job_input.get('generate_motion_template', True)

    if not source_image_url:
        return {"error": "source_image_url is required"}

    print(f"\n[Job] Starting LivePortrait animation")
    print(f"[Job] Source image: {source_image_url}")
    print(f"[Job] Expression: {expression}")
    print(f"[Job] Driving video: {driving_video_url or 'None (using expression preset)'}")

    # Create temp directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Download source image
        source_image_path = os.path.join(temp_dir, 'source.jpg')
        source_image_path, error = download_file(source_image_url, source_image_path)
        if error:
            return {"error": f"Failed to download source image: {error}"}

        # Download driving video if provided
        driving_video_path = None
        if driving_video_url:
            driving_video_path = os.path.join(temp_dir, 'driving.mp4')
            driving_video_path, error = download_file(driving_video_url, driving_video_path)
            if error:
                return {"error": f"Failed to download driving video: {error}"}

        # Generate animation
        output_video_path = os.path.join(temp_dir, 'output.mp4')
        output_motion_template_path = os.path.join(temp_dir, 'motion_template.pkl') if generate_motion_template else None

        video_path, template_path, error = generate_animation(
            source_image_path=source_image_path,
            driving_video_path=driving_video_path,
            expression=expression,
            output_video_path=output_video_path,
            output_motion_template_path=output_motion_template_path
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
