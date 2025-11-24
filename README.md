# LivePortrait RunPod Serverless

Facial animation with expression control using LivePortrait.

## Features

- **Expression Templates**: 9 built-in expression templates from LivePortrait (neutral, approve, disapprove, smile, sad, surprised, confused, wink, talking)
- **High Quality**: LivePortrait's efficient portrait animation (12.8ms on RTX 4090)
- **S3 Integration**: Automatic upload to RunPod S3
- **Based on Official LivePortrait**: Uses official KlingTeam/LivePortrait repository

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
    "expression": "smile"
  }
}
```

### Parameters

- **source_image_url** (required): URL to source portrait image
- **expression** (optional): Expression template - neutral, approve, disapprove, smile, sad, surprised, confused, wink, talking (default: "neutral")

### Expression Templates

| Expression | Template | Use Case |
|------------|----------|----------|
| neutral | d0.mp4 | Default, calm talking |
| approve | d1.pkl | Nodding, agreeing |
| disapprove | shake_face.pkl | Shaking head, disagreeing |
| smile | laugh.pkl | Happy, positive content |
| sad | aggrieved.pkl | Sad, serious content |
| surprised | d5.pkl | Excited, shocked reactions |
| confused | shy.pkl | Questioning, uncertain |
| wink | wink.pkl | Playful winking |
| talking | talking.pkl | Natural talking motion |

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
