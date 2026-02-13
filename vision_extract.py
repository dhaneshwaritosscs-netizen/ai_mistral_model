import os
import sys
import base64
import requests
from openai import OpenAI

# Initialize OpenAI client
# It will automatically look for OPENAI_API_KEY environment variable
client = OpenAI()

def encode_image(image_path):
    """Encode local image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def extract_text_vision(image_source):
    """
    Extract text from an image using OpenAI Vision API.
    Supports both local paths and URLs.
    """
    prompt = """
    Extract all readable text from this image. 
    Only output meaningful English text (A-Z, a-z, numbers, and basic punctuation).
    Ignore garbage characters, symbols, unreadable strings, or non-English characters completely.
    If the image contains no readable English text, return "No text found".
    Do not include any extra explanation, comments, or markdown formatting (output raw text only).
    """

    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        if image_source.startswith(("http://", "https://")):
            # It's a URL
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": image_source}
            })
        else:
            # It's a local file
            if not os.path.exists(image_source):
                return f"Error: File not found: {image_source}"
            
            base64_image = encode_image(image_source)
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vision_extract.py <image_path_or_url>")
        sys.exit(1)

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Please set it using: $env:OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    source = sys.argv[1]
    result = extract_text_vision(source)
    print(result)
