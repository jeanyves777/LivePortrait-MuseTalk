# LivePortrait RunPod Serverless
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

# Set working directory
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Clone LivePortrait repository
RUN git clone https://github.com/KwaiVGI/LivePortrait.git /workspace/LivePortrait

# Install Python dependencies
WORKDIR /workspace/LivePortrait
RUN pip install --no-cache-dir -r requirements.txt

# Download pretrained models from HuggingFace
# Use compatible huggingface_hub version that works with transformers 4.38.0 and tokenizers 0.15.2
RUN pip install --no-cache-dir "huggingface_hub>=0.19.3,<1.0" && \
    huggingface-cli download KlingTeam/LivePortrait --local-dir pretrained_weights --exclude "*.git*" "README.md" "docs"

# Copy handler
WORKDIR /workspace
COPY handler.py .
COPY requirements.txt .

# Install RunPod and additional dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the handler as the entry point
CMD ["python", "-u", "handler.py"]
