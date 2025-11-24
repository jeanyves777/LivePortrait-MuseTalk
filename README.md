# LivePortrait RunPod Serverless

Facial animation with expression control using LivePortrait.

## Features

- **Expression Presets**: 7 built-in expressions (neutral, approve, disapprove, smile, sad, surprised, confused)
- **Custom Driving**: Use custom driving videos for unique animations
- **Motion Templates**: Generate reusable motion templates for consistent animations
- **High Quality**: LivePortrait's efficient portrait animation (12.8ms on RTX 4090)
- **S3 Integration**: Automatic upload to RunPod S3

## Deployment to RunPod

### Step 1: Build Docker Image

```bash
cd /var/www/liveportrait-runpod
docker build -t your-dockerhub-username/liveportrait:latest .
docker push your-dockerhub-username/liveportrait:latest
```

### Step 2: Create RunPod Serverless Endpoint

1. Go to https://www.runpod.io/console/serverless
2. Click "New Endpoint"
3. Settings:
   - **Name**: liveportrait
   - **GPU Type**: RTX 4090 or A100
   - **Container Image**: `your-dockerhub-username/liveportrait:latest`
   - **Container Disk**: 30GB (models are large)
   - **Min Workers**: 0
   - **Max Workers**: 3
   - **Idle Timeout**: 60 seconds
   - **Environment Variables**:
     - `RUNPOD_S3_ACCESS_KEY`: Your S3 access key
     - `RUNPOD_S3_SECRET_KEY`: Your S3 secret key
     - `RUNPOD_S3_BUCKET`: flowsmartly-avatars
     - `RUNPOD_S3_ENDPOINT`: https://storage.runpod.io

## API Usage

### Input Parameters

```json
{
  "input": {
    "source_image_url": "https://example.com/portrait.jpg",
    "expression": "smile",
    "driving_video_url": "https://example.com/driving.mp4",
    "generate_motion_template": true
  }
}
```

### Parameters

- **source_image_url** (required): URL to source portrait image
- **expression** (optional): Expression preset - neutral, approve, disapprove, smile, sad, surprised, confused (default: "neutral")
- **driving_video_url** (optional): URL to custom driving video (overrides expression preset)
- **generate_motion_template** (optional): Generate reusable motion template (default: true)

### Expression Presets

| Expression | Index | Use Case |
|------------|-------|----------|
| neutral | 0 | Default, calm talking |
| approve | 1 | Nodding, agreeing |
| disapprove | 2 | Shaking head, disagreeing |
| smile | 3 | Happy, positive content |
| sad | 4 | Sad, serious content |
| surprised | 5 | Excited, shocked reactions |
| confused | 6 | Questioning, uncertain |

### Output

```json
{
  "video_url": "https://storage.runpod.io/bucket/liveportrait-output/output.mp4",
  "motion_template_url": "https://storage.runpod.io/bucket/liveportrait-output/motion_template.pkl",
  "expression": "smile",
  "status": "completed"
}
```

## Local Testing

```bash
python handler.py
```

Then test with:

```python
import requests

response = requests.post('http://localhost:8000/runsync', json={
    "input": {
        "source_image_url": "https://example.com/portrait.jpg",
        "expression": "smile"
    }
})

print(response.json())
```

## Integration with MuseTalk

LivePortrait output can be used as input for MuseTalk lip-sync:

1. **LivePortrait**: Generates facial animation with expression
2. **MuseTalk**: Applies lip-sync to the animated face
3. **Result**: High-quality talking avatar with natural expressions

## License

Based on LivePortrait (MIT) - https://github.com/KwaiVGI/LivePortrait

## References

- GitHub: https://github.com/KwaiVGI/LivePortrait
- Paper: LivePortrait: Efficient Portrait Animation with Stitching and Retargeting Control
- Performance: 12.8ms on RTX 4090
