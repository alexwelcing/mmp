#!/usr/bin/env python3
"""
Batch mint script for the first 10 AI-generated characters.

Usage:
    export API_URL=http://34.8.224.143
    python batch_mint.py
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx

API_URL = os.environ.get("API_URL", "http://34.8.224.143")
API_HOST = os.environ.get("API_HOST", "api.endlesse.dev")  # Required for GCE ingress

CHARACTERS = [
    {
        "user_id": "player_001",
        "preferences": {
            "role": "cyberpunk_hacker",
            "aesthetic": "neon_noir",
            "description": "A street-smart hacker with neon tattoos and a holographic visor"
        }
    },
    {
        "user_id": "player_002", 
        "preferences": {
            "role": "mystic_knight",
            "aesthetic": "ethereal_fantasy",
            "description": "An armored warrior wielding a sword made of starlight"
        }
    },
    {
        "user_id": "player_003",
        "preferences": {
            "role": "forest_druid",
            "aesthetic": "nature_magic",
            "description": "A guardian of ancient woods with living armor of bark and moss"
        }
    },
    {
        "user_id": "player_004",
        "preferences": {
            "role": "stealth_assassin",
            "aesthetic": "shadow_forged",
            "description": "A phantom-like figure wrapped in shadows and smoke"
        }
    },
    {
        "user_id": "player_005",
        "preferences": {
            "role": "tech_mage",
            "aesthetic": "arcane_cybernetics",
            "description": "A spellcaster who channels magic through cybernetic implants"
        }
    },
    {
        "user_id": "player_006",
        "preferences": {
            "role": "desert_wanderer",
            "aesthetic": "post_apocalyptic",
            "description": "A survivalist in tattered robes with sand-worn technology"
        }
    },
    {
        "user_id": "player_007",
        "preferences": {
            "role": "celestial_guardian",
            "aesthetic": "divine_light",
            "description": "A holy warrior with wings of golden light and crystalline armor"
        }
    },
    {
        "user_id": "player_008",
        "preferences": {
            "role": "necrotic_sorcerer",
            "aesthetic": "dark_fantasy",
            "description": "A master of death magic with glowing eyes and bone accessories"
        }
    },
    {
        "user_id": "player_009",
        "preferences": {
            "role": "pirate_captain",
            "aesthetic": "steampunk_ocean",
            "description": "A swashbuckler with mechanical limbs and a plasma cutlass"
        }
    },
    {
        "user_id": "player_010",
        "preferences": {
            "role": "quantum_ranger",
            "aesthetic": "sci_fi_western",
            "description": "A gunslinger with a phase-shifting revolver and holographic coat"
        }
    },
]


@dataclass
class MintResult:
    user_id: str
    job_id: Optional[str] = None
    status: str = "pending"
    image_url: Optional[str] = None
    error: Optional[str] = None


def get_client() -> httpx.AsyncClient:
    """Create HTTP client with proper headers for GCE ingress."""
    headers = {"Host": API_HOST} if API_HOST else {}
    return httpx.AsyncClient(headers=headers, timeout=30.0)


async def generate_character(
    client: httpx.AsyncClient, 
    character: dict
) -> MintResult:
    """Generate a single character."""
    user_id = character["user_id"]
    
    try:
        # Submit generation request
        response = await client.post(
            f"{API_URL}/generate",
            json=character,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        
        job_id = data.get("job_id")
        if not job_id:
            return MintResult(
                user_id=user_id,
                status="error",
                error="No job_id in response"
            )
        
        print(f"  {user_id}: Job {job_id[:8]}... submitted")
        
        # Poll for completion (max 5 minutes)
        for attempt in range(60):
            await asyncio.sleep(5)
            
            status_resp = await client.get(
                f"{API_URL}/status/{job_id}",
                timeout=10.0
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            
            stage = status_data.get("stage", "unknown")
            
            if stage == "complete":
                return MintResult(
                    user_id=user_id,
                    job_id=job_id,
                    status="completed",
                    image_url=status_data.get("upscaled_url") or status_data.get("selected_draft_url")
                )
            elif stage in ("failed", "error"):
                return MintResult(
                    user_id=user_id,
                    job_id=job_id,
                    status="failed",
                    error=status_data.get("error", "Unknown error")
                )
            
            if attempt % 6 == 0:  # Every 30s
                print(f"  {user_id}: Still processing... ({attempt * 5}s)")
        
        # Timeout
        return MintResult(
            user_id=user_id,
            job_id=job_id,
            status="timeout",
            error="Generation timed out after 5 minutes"
        )
        
    except httpx.HTTPStatusError as e:
        return MintResult(
            user_id=user_id,
            status="error",
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        return MintResult(
            user_id=user_id,
            status="error",
            error=str(e)
        )


async def batch_mint(concurrency: int = 3) -> list[MintResult]:
    """Mint all 10 characters with limited concurrency."""
    print(f"\n{'='*60}")
    print("BATCH MINT: First 10 AI-Generated Characters")
    print(f"{'='*60}")
    print(f"API: {API_URL}")
    print(f"Characters: {len(CHARACTERS)}")
    print(f"Concurrency: {concurrency}")
    print()
    
    # Check API health first
    async with get_client() as client:
        try:
            health = await client.get(f"{API_URL}/health", timeout=5.0)
            if health.status_code == 200:
                print(f"✓ API healthy: {health.text.strip()}")
            else:
                print(f"⚠ API returned {health.status_code}")
        except Exception as e:
            print(f"✗ API unreachable: {e}")
            return []
    
    print()
    
    # Process with semaphore for concurrency control
    semaphore = asyncio.Semaphore(concurrency)
    results: list[MintResult] = []
    
    async def process_with_limit(character: dict) -> MintResult:
        async with semaphore:
            async with get_client() as client:
                return await generate_character(client, character)
    
    # Run all generations
    tasks = [process_with_limit(c) for c in CHARACTERS]
    results = await asyncio.gather(*tasks)
    
    # Print summary
    print()
    print(f"{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    
    completed = sum(1 for r in results if r.status == "completed")
    failed = sum(1 for r in results if r.status in ("failed", "error", "timeout"))
    
    for r in results:
        status_icon = "✓" if r.status == "completed" else "✗"
        print(f"{status_icon} {r.user_id}: {r.status}")
        if r.image_url:
            print(f"    Image: {r.image_url}")
        if r.error:
            print(f"    Error: {r.error}")
    
    print()
    print(f"Completed: {completed}/{len(CHARACTERS)}")
    print(f"Failed: {failed}/{len(CHARACTERS)}")
    print()
    
    # Save results
    output_file = "batch_mint_results.json"
    with open(output_file, "w") as f:
        json.dump([
            {
                "user_id": r.user_id,
                "job_id": r.job_id,
                "status": r.status,
                "image_url": r.image_url,
                "error": r.error
            }
            for r in results
        ], f, indent=2)
    print(f"Results saved to: {output_file}")
    
    return results


def main():
    """Run batch mint."""
    # Allow command-line override of concurrency
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    
    try:
        results = asyncio.run(batch_mint(concurrency))
        
        # Exit with error code if any failed
        failed = sum(1 for r in results if r.status in ("failed", "error", "timeout"))
        if failed > 0:
            print(f"\n⚠ {failed} generations failed")
            sys.exit(1)
        else:
            print("\n✓ All characters generated successfully!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
