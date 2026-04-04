# MMP Audio Worker — Local audio generation via Facebook AudioGen.
#
# Uses Hugging Face Hub for model caching. Mount a volume to
# /root/.cache/huggingface to avoid re-downloading on every restart.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing and torch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    git \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the AudioGen model at build time (optional but speeds first startup).
# If you prefer to download at runtime (smaller image), comment this out.
# RUN python -c "from audiocraft.models import AudioGen; AudioGen.get_pretrained('facebook/audiogen-medium')"

# Copy application source.
COPY main.py .

# Output directory for generated audio files.
RUN mkdir -p /mnt/filestore/outputs/audio

EXPOSE 9000

CMD ["python", "main.py"]
