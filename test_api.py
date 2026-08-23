"""
test_api.py
Run this to check if your Google Cloud Vision API is working correctly.
Usage: python test_api.py
"""

import requests
import base64
import json
import sys
import os


GOOGLE_API_KEY = "AIzaSyBQcRIzQn0yy6Q9txtW8vxbqDV364datJo"

URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_API_KEY}"

def test_with_image(image_path):
    print(f"\n{'='*55}")
    print(f"Testing Google Cloud Vision API")
    print(f"Image: {image_path}")
    print(f"{'='*55}\n")

    # ── Step 1: Check internet ──
    print("Step 1: Checking internet connection...")
    try:
        r = requests.get("https://google.com", timeout=5)
        print("  ✓ Internet is working\n")
    except Exception as e:
        print(f"  ✗ No internet: {e}")
        print("  Fix: Connect to internet and try again")
        return

    # ── Step 2: Check image exists ──
    print(f"Step 2: Checking image file...")
    if not os.path.exists(image_path):
        print(f"  ✗ Image not found: {image_path}")
        print("  Fix: Give correct path to your prescription image")
        return
    print(f"  ✓ Image found: {os.path.getsize(image_path)} bytes\n")

    # ── Step 3: Call API ──
    print("Step 3: Calling Google Cloud Vision API...")
    with open(image_path, "rb") as f:
        image_content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "requests": [{
            "image": {"content": image_content},
            "features": [
                {"type": "DOCUMENT_TEXT_DETECTION", "maxResults": 1}
            ],
            "imageContext": {"languageHints": ["en", "hi"]}
        }]
    }

    try:
        response = requests.post(URL, json=payload, timeout=30)
        print(f"  HTTP Status: {response.status_code}")

        if response.status_code == 200:
            print("  ✓ API responded successfully!\n")
        elif response.status_code == 400:
            print("  ✗ Bad request — image may be corrupted")
            print(f"  Response: {response.text[:300]}")
            return
        elif response.status_code == 403:
            print("  ✗ API KEY ERROR — key is invalid or API not enabled!")
            print(f"  Response: {response.text[:300]}")
            print("\n  Fix steps:")
            print("  1. Go to https://console.cloud.google.com")
            print("  2. Enable 'Cloud Vision API' for your project")
            print("  3. Check your API key restrictions")
            return
        elif response.status_code == 429:
            print("  ✗ Quota exceeded — too many requests")
            return
        else:
            print(f"  ✗ Unexpected status: {response.status_code}")
            print(f"  Response: {response.text[:300]}")
            return

        # ── Step 4: Show raw text from API ──
        result = response.json()
        resp0  = result.get("responses", [{}])[0]

        if "error" in resp0:
            print(f"  ✗ API Error: {resp0['error']}")
            return

        full_text = ""
        if "fullTextAnnotation" in resp0:
            full_text = resp0["fullTextAnnotation"].get("text", "")
        elif "textAnnotations" in resp0:
            full_text = resp0["textAnnotations"][0].get("description", "")

        if full_text:
            print("Step 4: RAW TEXT from Cloud Vision API:")
            print("-" * 40)
            print(full_text)
            print("-" * 40)
            print(f"\n✓ API is WORKING! Detected {len(full_text)} characters.")
            print("\nIf medicines are missing from your results,")
            print("the issue is in the medicine matching logic, not the API.")
        else:
            print("  ✗ API returned no text!")
            print("  The image may be too dark/blurry for Cloud Vision.")
            print("  Try taking a clearer photo in better lighting.")

    except requests.exceptions.Timeout:
        print("  ✗ Request timed out — slow internet or API down")
    except Exception as e:
        print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    # ── If you pass an image path as argument, use that ──
    if len(sys.argv) > 1:
        test_with_image(sys.argv[1])
    else:
        # ── Otherwise ask for path ──
        print("Enter the full path to your prescription image.")
        print(r"Example: C:\Users\rajac\med_assistant\uploads\nandini.jpeg")
        path = input("\nImage path: ").strip().strip('"')
        test_with_image(path)