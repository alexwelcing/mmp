# ComfyUI Worker — GPU-enabled Docker image
# Extends the official ComfyUI image with custom workflows and node packs.

FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime AS base

# System dependencies for ComfyUI and custom nodes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone ComfyUI at a pinned commit for reproducibility.
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI \
    && cd /app/ComfyUI \
    && git checkout v0.2.7

WORKDIR /app/ComfyUI

# Install ComfyUI Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Install custom node packs:
#   - comfyui-manager: Node management UI
#   - ComfyUI-3DGS: 3D Gaussian Splatting generation
#   - comfyui-clarity-upscaler: High-quality 4x upscaling
RUN cd custom_nodes \
    && git clone https://github.com/ltdrdata/ComfyUI-Manager.git \
    && git clone https://github.com/MrForExample/ComfyUI-3D-Pack.git \
    && git clone https://github.com/philz1337x/comfyui-clarity-upscaler.git

# Install dependencies for each custom node pack.
RUN for dir in custom_nodes/*/; do \
    if [ -f "${dir}requirements.txt" ]; then \
        pip install --no-cache-dir -r "${dir}requirements.txt"; \
    fi; \
done

# Copy our custom workflows into the ComfyUI workflows directory.
COPY workflows/ /app/ComfyUI/workflows/custom/

# Copy the AI Director webhook custom node.
COPY custom_nodes/ai_director_webhook /app/ComfyUI/custom_nodes/ai_director_webhook

# The Filestore NFS mount will provide pre-downloaded models at runtime.
# This avoids downloading multi-GB model files on every container start.
# Mount point: /mnt/filestore/models → /app/ComfyUI/models (symlink)
RUN ln -s /mnt/filestore/models /app/ComfyUI/models || true

# Output directory symlinked to Filestore for durable storage.
RUN mkdir -p /mnt/filestore/outputs \
    && ln -sf /mnt/filestore/outputs /app/ComfyUI/output || true

EXPOSE 8188

# Start ComfyUI with --listen to allow external connections from the
# AI Director service.
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", \
     "--disable-xformers", "--lowvram"]
