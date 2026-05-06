#!/usr/bin/env python3
"""Simple test for HF provider - run after pip install -r requirements.txt"""

import os
import sys

def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    
    # Test huggingface_hub
    from huggingface_hub import InferenceClient
    print("✓ huggingface_hub imported")
    
    # Test PIL
    from PIL import Image
    print("✓ PIL imported")
    
    # Test pydantic
    from pydantic import Field, HttpUrl
    print("✓ pydantic imported")
    
    print()

def test_dataclass():
    """Test GeneratedImage dataclass."""
    print("Testing GeneratedImage dataclass...")
    from dataclasses import dataclass
    from typing import Any
    
    @dataclass
    class GeneratedImage:
        url: str
        width: int = 1024
        height: int = 1024
        metadata: dict[str, Any] | None = None
    
    img = GeneratedImage(url="/test.png", width=512, height=512)
    print(f"✓ GeneratedImage: {img}")
    print()

def test_hf_client_creation():
    """Test HF client can be created (without token)."""
    print("Testing HF client creation...")
    from huggingface_hub import InferenceClient
    
    token = os.environ.get("HF_TOKEN", "")
    if token:
        client = InferenceClient(token=token)
        print(f"✓ InferenceClient created with token")
    else:
        client = InferenceClient()
        print("✓ InferenceClient created (no token - will use anonymous)")
    print()

def test_settings_structure():
    """Test that config has the new fields."""
    print("Testing settings structure...")
    
    # Read the config file
    with open("config.py") as f:
        content = f.read()
    
    assert "image_provider" in content, "image_provider field missing"
    assert "huggingface_token" in content, "huggingface_token field missing"
    assert "Literal[\"comfyui\", \"huggingface\"]" in content, "provider literal type missing"
    
    print("✓ config.py has image_provider and huggingface_token fields")
    print()

def test_provider_file_structure():
    """Test provider file has all required components."""
    print("Testing provider file structure...")
    
    with open("agents/providers/image_provider.py") as f:
        content = f.read()
    
    checks = [
        ("ImageProvider ABC", "class ImageProvider(ABC)"),
        ("HuggingFaceProvider", "class HuggingFaceProvider(ImageProvider)"),
        ("ComfyUIProvider", "class ComfyUIProvider(ImageProvider)"),
        ("ImageProviderFactory", "class ImageProviderFactory"),
        ("GeneratedImage dataclass", "class GeneratedImage"),
        ("create method", "def create("),
        ("generate_image method", "async def generate_image"),
        ("upscale_image method", "async def upscale_image"),
    ]
    
    for name, pattern in checks:
        assert pattern in content, f"{name} missing"
        print(f"  ✓ {name}")
    
    print()

def test_image_agent_integration():
    """Test ImageAgent has provider integration."""
    print("Testing ImageAgent integration...")
    
    with open("agents/image_agent.py") as f:
        content = f.read()
    
    checks = [
        ("provider import", "from .providers.image_provider import"),
        ("provider parameter", "provider: ImageProvider | None = None"),
        ("provider assignment", "self._provider = provider"),
        ("provider check", "if self._provider:"),
    ]
    
    for name, pattern in checks:
        assert pattern in content, f"{name} missing"
        print(f"  ✓ {name}")
    
    print()

def test_orchestrator_integration():
    """Test orchestrator uses factory."""
    print("Testing Orchestrator integration...")
    
    with open("agents/orchestrator.py") as f:
        content = f.read()
    
    checks = [
        ("factory import", "from .providers.image_provider import ImageProviderFactory"),
        ("factory usage", "ImageProviderFactory.create(settings)"),
    ]
    
    for name, pattern in checks:
        assert pattern in content, f"{name} missing"
        print(f"  ✓ {name}")
    
    print()

def test_requirements():
    """Test requirements.txt has HF deps."""
    print("Testing requirements.txt...")
    
    with open("requirements.txt") as f:
        content = f.read()
    
    assert "huggingface-hub" in content, "huggingface-hub missing"
    assert "pillow" in content, "pillow missing"
    
    print("✓ huggingface-hub in requirements.txt")
    print("✓ pillow in requirements.txt")
    print()

def main():
    print("\n" + "=" * 60)
    print("HUGGING FACE PROVIDER - STRUCTURE TESTS")
    print("=" * 60 + "\n")
    
    test_imports()
    test_dataclass()
    test_hf_client_creation()
    test_settings_structure()
    test_provider_file_structure()
    test_image_agent_integration()
    test_orchestrator_integration()
    test_requirements()
    
    print("=" * 60)
    print("ALL STRUCTURE TESTS PASSED ✓")
    print("=" * 60)
    print()
    print("Next steps to deploy:")
    print("  1. Build Docker image:")
    print("     cd services/ai-director")
    print("     docker build -t us-central1-docker.pkg.dev/endlesse/mmp/ai-director:hf .")
    print("     docker push us-central1-docker.pkg.dev/endlesse/mmp/ai-director:hf")
    print()
    print("  2. Deploy to cluster:")
    print("     cd infrastructure/pulumi")
    print("     pulumi up -s hybrid")
    print()
    print("  3. Test generation:")
    print("     curl -X POST http://34.8.224.143/generate \\")
    print("       -H 'Content-Type: application/json' \\")
    print("       -d '{\"user_id\":\"user_001\",\"preferences\":{\"role\":\"warrior\"}}'")

if __name__ == "__main__":
    main()
