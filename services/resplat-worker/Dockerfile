# ReSplat Worker — GPU-enabled container for recurrent 3D Gaussian Splatting
# https://github.com/cvg/resplat
#
# NOTE: ReSplat requires PyTorch 2.7.0 + CUDA 12.8, which is newer than the
# ComfyUI worker base image. Therefore it runs as a separate service.

FROM pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime AS base

# System dependencies for COLMAP, OpenCV, and build tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    colmap \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone ReSplat at a pinned commit for reproducibility.
RUN git clone https://github.com/cvg/resplat.git /app/resplat \
    && cd /app/resplat \
    && git checkout cc4594af97a2e559e98f5e307d80535569ae7007

WORKDIR /app/resplat

# Install Python dependencies.
COPY requirements.txt /app/resplat/requirements-worker.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-worker.txt

# Install gsplat 1.5.3 (required by ReSplat).
RUN pip install --no-build-isolation \
    git+https://github.com/nerfstudio-project/gsplat.git@v1.5.3

# Install pointops (kNN) used by the encoder.
RUN cd src/model/encoder/pointops \
    && python setup.py install \
    && cd /app/resplat

# Pre-trained model weights are expected to be mounted at /mnt/filestore/resplat/pretrained
# via the shared Filestore NFS volume.  Symlink it to the location ReSplat expects.
RUN ln -s /mnt/filestore/resplat/pretrained /app/resplat/pretrained || true

# Output directory for generated .ply files.
RUN mkdir -p /mnt/filestore/resplat/outputs \
    && ln -sf /mnt/filestore/resplat/outputs /app/resplat/outputs || true

# Copy our inference wrapper.
COPY infer.py /app/resplat/infer.py
COPY entrypoint.sh /app/resplat/entrypoint.sh
RUN chmod +x /app/resplat/entrypoint.sh

EXPOSE 9001

ENTRYPOINT ["/app/resplat/entrypoint.sh"]
