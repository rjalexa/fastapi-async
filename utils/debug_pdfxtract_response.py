#!/usr/bin/env python3
"""
Debug script to test what OpenRouter API returns for pdfxtract requests.
"""

import asyncio
import base64
import io
import json
import sys
from pathlib import Path

import httpx
from pdf2image import convert_from_bytes

# Import from worker modules
sys.path.append('src/worker')
from config import settings
from prompts import load_prompt


async def test_openrouter_pdfxtract():
    """Test OpenRouter API response for pdfxtract."""
    
    # Check if we have the required settings
    if not settings.openrouter_api_key:
        print("❌ OpenRouter API key not configured")
        return
    
    print(f"🔑 Using OpenRouter API key: {settings.openrouter_api_key[:10]}...")
    print(f"🤖 Using model: {settings.openrouter_model}")
    print(f"🌐 Base URL: {settings.openrouter_base_url}")
    
    # Load the PDF file
    pdf_path = Path("docs/il-manifesto-del-31-dicembre-2023.pdf")
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return
    
    print(f"📄 Loading PDF: {pdf_path}")
    
    # Read and encode PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    pdf_content_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    print(f"📊 PDF size: {len(pdf_bytes)} bytes, base64 size: {len(pdf_content_b64)} chars")
    
    # Convert first page to image
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=300, fmt="PNG")
        print(f"📖 Converted PDF to {len(pages)} pages")
    except Exception as e:
        print(f"❌ PDF conversion failed: {e}")
        return
    
    if not pages:
        print("❌ No pages found in PDF")
        return
    
    # Process first page only
    page_image = pages[0]
    print(f"🖼️ Processing page 1, size: {page_image.size}")
    
    # Convert PIL Image to base64
    img_buffer = io.BytesIO()
    page_image.save(img_buffer, format="PNG")
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode("utf-8")
    print(f"🖼️ Image base64 size: {len(img_base64)} chars")
    
    # Load the prompt
    try:
        system_prompt = load_prompt("pdfxtract")
        print(f"📝 Loaded prompt, length: {len(system_prompt)} chars")
        print(f"📝 Prompt preview: {system_prompt[:200]}...")
    except Exception as e:
        print(f"❌ Failed to load prompt: {e}")
        return
    
    # Create the messages payload
    user_content = f"Analyze this newspaper page image. Filename: {pdf_path.name}, Page number: 1, Issue date: 2023-12-31"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_content},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    },
                },
            ],
        },
    ]
    
    print(f"💬 Created messages payload with {len(messages)} messages")
    print(f"💬 User message content length: {len(str(messages[1]))}")
    
    # Make the API call
    try:
        async with httpx.AsyncClient() as client:
            print("🚀 Making API call to OpenRouter...")
            
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": messages,
                },
                timeout=settings.openrouter_timeout,
            )
            
            print(f"📡 Response status: {response.status_code}")
            print(f"📡 Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                print(f"❌ API error: {response.status_code}")
                print(f"❌ Response text: {response.text}")
                return
            
            result = response.json()
            print(f"✅ API call successful")
            print(f"📊 Response keys: {list(result.keys())}")
            
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                print(f"📝 Content length: {len(content)} chars")
                print(f"📝 Content preview (first 500 chars):")
                print("-" * 50)
                print(content[:500])
                print("-" * 50)
                
                # Try to parse as JSON
                try:
                    parsed_json = json.loads(content)
                    print("✅ Content is valid JSON")
                    print(f"📊 JSON keys: {list(parsed_json.keys())}")
                    
                    if "pages" in parsed_json:
                        pages_data = parsed_json["pages"]
                        print(f"📖 Found {len(pages_data)} pages in response")
                        for i, page in enumerate(pages_data):
                            print(f"   Page {i+1}: status={page.get('status')}, articles={len(page.get('articles', []))}")
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Content is NOT valid JSON: {e}")
                    print("🔍 Checking for common issues...")
                    
                    # Check for markdown code blocks
                    if "```json" in content or "```" in content:
                        print("⚠️  Found markdown code blocks in response")
                    
                    # Check if it's empty or whitespace
                    if not content.strip():
                        print("⚠️  Response content is empty or whitespace only")
                    
                    # Check for common prefixes
                    if content.strip().startswith("Here"):
                        print("⚠️  Response starts with explanatory text")
                    
                    # Show the actual content for debugging
                    print("🔍 Full content for debugging:")
                    print(repr(content))
            else:
                print("❌ No choices found in response")
                print(f"📊 Full response: {result}")
                
    except Exception as e:
        print(f"❌ API call failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_openrouter_pdfxtract())
