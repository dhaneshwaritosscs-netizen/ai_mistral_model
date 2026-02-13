import sys
import os
import uuid
import requests
import re

# Add parent directory to path to find ocr.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ocr import ocr_easyocr, ocr_pytesseract

def convert_google_drive_link(url):
    """Convert Google Drive view link to direct download link"""
    if 'drive.google.com' in url and '/file/d/' in url:
        try:
            file_id = url.split('/file/d/')[1].split('/')[0]
            return f'https://drive.google.com/uc?export=download&id={file_id}'
        except:
            return url
    return url

def download_image(url):
    """Download image from URL to a temporary file"""
    try:
        # Handle Google Drive links
        url = convert_google_drive_link(url)
        
        # User-Agent headers to look like a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        
        # Get extension or default to jpg
        ext = 'jpg'
        if 'content-type' in response.headers:
            ct = response.headers['content-type']
            if 'image/' in ct:
                ext = ct.split('/')[-1]
        
        temp_filename = f"tmp_extract_{uuid.uuid4().hex}.{ext}"
        
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return temp_filename
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

def filter_garbage_text(text):
    """
    Filter out garbage text, symbols, and non-English characters.
    Returns "No text found" if result is empty.
    """
    if not text:
        return "No text found"
        
    cleaned_lines = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. Characters: Keep English alphanumeric and basic punctuation
        cleaned_line = re.sub(r'[^A-Za-z0-9\s.,!?;:()\'"₹$€£%-]', '', line).strip()
        
        if not cleaned_line:
            continue
            
        # 2. Heuristics to determine if the line is meaningful
        words = [w for w in cleaned_line.split() if w]
        
        # Check for price-like patterns (currency symbol or digits with decimal/comma)
        is_price = any(c in cleaned_line for c in '₹$€£') or bool(re.search(r'\d+[.,]\d+', cleaned_line))
        
        # Check for English-like words:
        # Require at least one word of 4+ characters OR at least two words of 3+ characters
        # For length check, we only count alphabetic characters
        alpha_words = ["".join(filter(str.isalpha, w)) for w in words]
        long_words = [w for w in alpha_words if len(w) >= 4]
        mid_words = [w for w in alpha_words if len(w) >= 3]
        
        has_real_word = len(long_words) >= 1 or len(mid_words) >= 2
        
        # Filter out lines that are just a collection of noise
        if is_price or has_real_word:
            # Final check: skip if line is mostly just short noise fragments
            if len(cleaned_line) > 2:
                cleaned_lines.append(cleaned_line)
            
    result = "\n".join(cleaned_lines).strip()
    return result if result else "No text found"

def extract_text(image_source):
    """
    Extract text from an image (path or URL) using EasyOCR (primary) and Tesseract (fallback).
    Prints the raw extracted text to stdout.
    """
    temp_file = None
    image_path = image_source

    # Check if input is a URL
    if image_source.startswith(('http://', 'https://')):
        print(f"Downloading image from: {image_source}")
        temp_file = download_image(image_source)
        if not temp_file:
            print("Failed to download image.")
            return
        image_path = temp_file
    elif not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return

    print(f"Processing image: {image_path}")
    print("-" * 40)

    try:
        # Try EasyOCR first (includes Hindi support for Rupee symbol)
        print("Running EasyOCR...")
        easyocr_text = ocr_easyocr(image_path, lang_list=['en', 'hi'])
        
        # Check if EasyOCR result is sufficient
        if len(easyocr_text.strip()) > 50:
            extracted_text = filter_garbage_text(easyocr_text)
            print(f"EasyOCR success.")
        else:
            print("EasyOCR text insufficient. Running Tesseract fallback...")
            try:
                tesseract_text = ocr_pytesseract(image_path)
            except Exception as e:
                print(f"Tesseract failed: {e}")
                tesseract_text = ""
            
            # Use the better result
            if len(tesseract_text) > len(easyocr_text):
                extracted_text = filter_garbage_text(tesseract_text)
            else:
                extracted_text = filter_garbage_text(easyocr_text)

        print("-" * 40)
        print("EXTRACTED TEXT:")
        print("-" * 40)
        print(extracted_text)
        print("-" * 40)

    except Exception as e:
        print(f"Error extracting text: {e}")
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                print(f"Warning: Could not remove temp file {temp_file}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <image_path_or_url>")
    else:
        extract_text(sys.argv[1])
