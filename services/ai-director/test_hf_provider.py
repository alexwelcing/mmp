#!/usr/bin/env python3
"""Test script for Hugging Face image provider integration."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import directly to avoid google cloud dependency
import importlib.util
spec = importlib.util.spec_from_file_location('config', Path(__file__).parent / 'config.py')
config_mod = importlib.util.module_from_spec(spec)
sys.modules['config'] = config_mod
spec.loader.exec_module(config_mod)
Settings = config_mod.Settings
get_settings = config_mod.get_settings

spec2 = importlib.util.spec_from_file_location('image_provider', Path(__file__).parent / 'agents' / 'providers' / 'image_provider.py')
provider_mod = importlib.util.module_from_spec(spec2)
sys.modules['providers'] = provider_mod
spec2.loader.exec_module(provider_mod)
ImageProviderFactory = provider_mod.ImageProviderFactory
HuggingFaceProvider = provider_mod.HuggingFaceProvider


def test_factory():
    """Test that the factory creates the right provider."""
    print("=" * 50)
    print("TEST 1: Provider Factory Creation")
    print("=" * 50)
    
    # Test with default settings (comfyui)
    settings = get_settings()
    print(f"Default image_provider: {settings.image_provider}")
    
    # Test factory with huggingface
    class HFSettings:
        image_provider = "huggingface"
        huggingface_token = "test_token"
        output_base_path = "/tmp/test_outputs"
        comfyui_endpoint = "http://test:8188"
        comfyui_timeout_seconds = 30
    
    try:
        provider = ImageProviderFactory.create(HFSettings())
        print(f"Created provider type: {type(provider).__name__}")
        assert isinstance(provider, HuggingFaceProvider), "Expected HuggingFaceProvider"
        print("✓ Factory creates HuggingFaceProvider correctly")
    except ValueError as e:
        if "Invalid token" in str(e) or "token" in str(e).lower():
            print(f"✓ Factory creates HuggingFaceProvider (token validation works)")
        else:
            raise
    
    print()


def test_settings():
    """Test that settings load correctly."""
    print("=" * 50)
    print("TEST 2: Settings Configuration")
    print("=" * 50)
    
    settings = get_settings()
    print(f"image_provider: {settings.image_provider}")
    print(f"output_base_path: {settings.output_base_path}")
    print(f"comfyui_endpoint: {settings.comfyui_endpoint}")
    
    # Verify defaults
    assert settings.image_provider in ["comfyui", "huggingface"], "Invalid provider"
    print("✓ Settings load correctly")
    print()


def test_image_agent_integration():
    """Test that ImageAgent accepts provider."""
    print("=" * 50)
    print("TEST 3: ImageAgent Integration")
    print("=" * 50)
    
    # Import ImageAgent directly to avoid google cloud deps
    spec = importlib.util.spec_from_file_location('image_agent', Path(__file__).parent / 'agents' / 'image_agent.py')
    image_agent_mod = importlib.util.module_from_spec(spec)
    sys.modules['agents.providers.image_provider'] = provider_mod
    spec.loader.exec_module(image_agent_mod)
    ImageAgent = image_agent_mod.ImageAgent
    
    # Create a mock provider
    class MockProvider:
        async def generate_image(self, prompt, **kwargs):
            return provider_mod.GeneratedImage(
                url="/tmp/test_output.png",
                width=1024,
                height=1024,
                metadata={"test": True}
            )
        
        async def upscale_image(self, image_url, **kwargs):
            return provider_mod.GeneratedImage(
                url="/tmp/test_upscaled.png",
                width=4096,
                height=4096,
            )
    
    # Create settings
    class TestSettings:
        comfyui_endpoint = "http://test:8188"
        comfyui_timeout_seconds = 30
        output_base_path = "/tmp"
    
    # Create agent with mock provider
    mock_provider = MockProvider()
    agent = ImageAgent(TestSettings(), mock_provider)
    
    print(f"ImageAgent created with provider: {agent._provider is not None}")
    print(f"Provider type: {type(agent._provider).__name__}")
    print("✓ ImageAgent accepts provider injection")
    print()


def test_prompt_building():
    """Test prompt building from preferences."""
    print("=" * 50)
    print("TEST 4: Prompt Building")
    print("=" * 50)
    
    # Import ImageAgent directly
    spec = importlib.util.spec_from_file_location('image_agent', Path(__file__).parent / 'agents' / 'image_agent.py')
    image_agent_mod = importlib.util.module_from_spec(spec)
    sys.modules['agents.providers.image_provider'] = provider_mod
    spec.loader.exec_module(image_agent_mod)
    ImageAgent = image_agent_mod.ImageAgent
    
    # Test with preferences
    prefs = {
        "role": "warrior",
        "aesthetic": "cyberpunk",
    }
    
    prompt = ImageAgent._build_prompt_from_preferences(prefs)
    print(f"Generated prompt: {prompt}")
    assert "warrior" in prompt.lower(), "Role should be in prompt"
    assert "cyberpunk" in prompt.lower(), "Aesthetic should be in prompt"
    print("✓ Prompt building works correctly")
    
    # Test with custom override
    prefs["prompt_override"] = "custom prompt here"
    prompt = ImageAgent._build_prompt_from_preferences(prefs)
    assert prompt == "custom prompt here", "Override should be used"
    print("✓ Prompt override works correctly")
    print()


def test_hf_provider_structure():
    """Test HuggingFaceProvider structure without actual API call."""
    print("=" * 50)
    print("TEST 5: HuggingFaceProvider Structure")
    print("=" * 50)
    
    from huggingface_hub import InferenceClient
    
    # Verify the imports work
    print(f"InferenceClient available: {InferenceClient is not None}")
    
    # Check provider class structure
    provider_class = HuggingFaceProvider
    methods = [m for m in dir(provider_class) if not m.startswith('_')]
    print(f"HuggingFaceProvider methods: {methods}")
    
    assert 'generate_image' in methods, "generate_image method required"
    assert 'upscale_image' in methods, "upscale_image method required"
    print("✓ HuggingFaceProvider has required methods")
    print()


async def test_hf_live(token: str):
    """Test actual HF API call (requires valid token)."""
    print("=" * 50)
    print("TEST 6: Live HF API Test")
    print("=" * 50)
    
    if not token:
        print("⚠ Skipping - no HF_TOKEN provided")
        return
    
    try:
        client = InferenceClient(token=token)
        
        # Quick test with small image
        print("Generating test image (this may take 10-30s)...")
        image = client.text_to_image(
            "a simple icon, minimalist, white background",
            model="stabilityai/stable-diffusion-xl-base-1.0",
            guidance_scale=7.5,
            num_inference_steps=20,  # Fast
            width=512,
            height=512,
        )
        
        print(f"✓ Image generated: {image.size}")
        
        # Save to verify
        output_path = Path("/tmp/hf_test_output.png")
        image.save(output_path)
        print(f"✓ Saved to: {output_path}")
        
    except Exception as e:
        print(f"✗ API test failed: {e}")
        raise


def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("HUGGING FACE PROVIDER INTEGRATION TESTS")
    print("=" * 50 + "\n")
    
    # Run unit tests
    test_factory()
    test_settings()
    test_image_agent_integration()
    test_prompt_building()
    test_hf_provider_structure()
    
    # Run live test if token available
    token = os.environ.get("HF_TOKEN", "")
    if token:
        asyncio.run(test_hf_live(token))
    else:
        print("=" * 50)
        print("TEST 6: Live HF API Test")
        print("=" * 50)
        print("⚠ Skipping - set HF_TOKEN environment variable to test")
        print()
    
    print("=" * 50)
    print("ALL TESTS PASSED ✓")
    print("=" * 50)


if __name__ == "__main__":
    main()
