#!/usr/bin/env python3
"""
Simple test script for OpenRouter credit monitoring without Redis dependency.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings


class TestSettings(BaseSettings):
    """Settings for OpenRouter credit testing."""
    
    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL"
    )
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # Ignore extra environment variables
    }


async def test_openrouter_credits(api_key: str, base_url: str) -> Dict:
    """Test OpenRouter API connection and credit fetching."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/auth/key",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            print("✅ OpenRouter API Response:")
            print(json.dumps(data, indent=2))
            
            # Extract usage information
            if isinstance(data, dict) and "data" in data:
                data_section = data["data"]
                total_usage = data_section.get("usage", 0.0)
                rate_limit = data_section.get("rate_limit", {})
                
                print(f"\n📊 Usage Summary:")
                print(f"   Total Usage: ${total_usage:.4f}")
                print(f"   Rate Limit: {rate_limit}")
                
                return {
                    "success": True,
                    "usage": total_usage,
                    "rate_limit": rate_limit,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {"success": False, "error": "Unexpected response format"}
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Main test function."""
    settings = TestSettings()
    
    if not settings.openrouter_api_key:
        print("❌ OpenRouter API key not configured. Please set OPENROUTER_API_KEY environment variable.")
        return
    
    print("🔍 Testing OpenRouter API connection...")
    result = await test_openrouter_credits(settings.openrouter_api_key, settings.openrouter_base_url)
    
    if result["success"]:
        print("\n✅ OpenRouter API test successful!")
    else:
        print(f"\n❌ OpenRouter API test failed: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())
