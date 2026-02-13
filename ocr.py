from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import easyocr
import platform
import numpy as np

# Windows tesseract path configuration (if needed)
# Uncomment and set path if tesseract is not in PATH
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_image_for_ocr(image_path: str, aggressive: bool = False) -> Image.Image:
    """
    Preprocess image to improve OCR accuracy, especially for numbers (price/MRP).
    Enhances contrast, sharpness, and converts to grayscale for better text recognition.
    
    Args:
        image_path: Path to the image file
        aggressive: If True, applies more aggressive preprocessing (may degrade quality)
    
    Returns:
        PIL.Image: Preprocessed image
    """
    img = Image.open(image_path)
    
    # Convert to RGB if needed (handles RGBA, P, etc.)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Convert to grayscale for better OCR (especially for numbers)
    img = img.convert('L')
    
    # Use moderate enhancement to avoid degrading text quality
    # Reduced from 2.0 to 1.5 to prevent over-processing
    contrast_factor = 2.0 if aggressive else 1.5
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast_factor)
    
    # Moderate sharpness enhancement (reduced from 2.0 to 1.3)
    sharpness_factor = 2.0 if aggressive else 1.3
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(sharpness_factor)
    
    # Apply slight denoising filter (only if aggressive)
    if aggressive:
        img = img.filter(ImageFilter.MedianFilter(size=3))
    
    # Resize if image is too small (OCR works better on larger images)
    width, height = img.size
    if width < 800 or height < 600:
        # Scale up small images
        scale_factor = max(800 / width, 600 / height)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return img

def ocr_pytesseract(image_path: str, aggressive: bool = False) -> str:
    """
    Extract text from image using pytesseract with enhanced preprocessing.
    Optimized for better number recognition (price/MRP).
    Preserves line-by-line structure from the screenshot.
    
    Args:
        image_path: Path to the image file
        aggressive: If True, uses aggressive preprocessing (may degrade quality)
    
    Returns:
        str: Extracted text with line breaks preserved
    """
    # Preprocess image for better OCR (use moderate preprocessing by default)
    img = preprocess_image_for_ocr(image_path, aggressive=aggressive)
    
    # Use config optimized for better number recognition
    # psm 6 = Assume a single uniform block of text (best general purpose)
    try:
        text = pytesseract.image_to_string(img, config='--psm 6')
        return text
    except:
        return ""
    return text

# optional (usually better on product pages with mixed fonts)
_reader = None
_reader_initialized = False
_read_count = 0
_MAX_READS_BEFORE_RESET = 50  # Reset reader after 50 reads to prevent memory issues

def ocr_easyocr(image_path: str, lang_list=['en'], force_reset: bool = False) -> str:
    """
    Extract text from image using easyocr with enhanced preprocessing.
    Optimized for better number recognition (price/MRP).
    Preserves line-by-line structure from the screenshot.
    
    Args:
        image_path: Path to the image file
        lang_list: List of language codes to use
        force_reset: Force reset of EasyOCR reader (useful if quality degrades)
    
    Returns:
        str: Extracted text with line breaks preserved
    """
    global _reader, _reader_initialized, _read_count
    
    # Reset reader if needed to prevent memory/quality degradation
    if force_reset or _read_count >= _MAX_READS_BEFORE_RESET:
        if _reader is not None:
            try:
                del _reader
            except:
                pass
            _reader = None
            _reader_initialized = False
            _read_count = 0
            print("EasyOCR reader reset to prevent degradation")
    
    if _reader is None:
        try:
            _reader = easyocr.Reader(lang_list, gpu=False, verbose=False)  # set gpu=True if available
            _reader_initialized = True
            _read_count = 0
        except Exception as e:
            print(f"Warning: EasyOCR reader initialization failed: {e}")
            return ""
    
    _read_count += 1
    
    # Preprocess image for better OCR (use moderate preprocessing)
    img = preprocess_image_for_ocr(image_path, aggressive=False)
    
    # Save preprocessed image temporarily for EasyOCR
    import tempfile
    import os
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            temp_path = tmp_file.name
            img.save(temp_path, 'PNG')
        
        # Get detailed results with bounding boxes to preserve line structure
        # Use allowlist parameter to prioritize numbers and currency symbols for better price/MRP extraction
        # Include all common characters but prioritize digits
        results = _reader.readtext(temp_path, detail=1)
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
    
    # Sort by vertical position (top to bottom) to maintain line order
    # Then group by similar Y coordinates to form lines
    if not results:
        return ""
    
    # Sort by top Y coordinate (top to bottom) to preserve vertical order
    sorted_results = sorted(results, key=lambda x: x[0][0][1])  # Sort by top-left Y coordinate
    
    if not sorted_results:
        return ""
    
    # Calculate average line height dynamically from the results
    y_coords = [item[0][0][1] for item in sorted_results]
    if len(y_coords) > 1:
        y_diffs = [y_coords[i+1] - y_coords[i] for i in range(len(y_coords)-1) if y_coords[i+1] > y_coords[i]]
        if y_diffs:
            # Use median of positive differences as line height
            y_diffs_sorted = sorted(y_diffs)
            line_height = y_diffs_sorted[len(y_diffs_sorted)//2] if y_diffs_sorted else 30
        else:
            line_height = 30
    else:
        line_height = 30
    
    # Group text boxes by similar Y coordinates (same line)
    lines = []
    current_line = []
    current_y = None
    
    for (bbox, text, confidence) in sorted_results:
        top_y = bbox[0][1]  # Top Y coordinate
        
        if current_y is None or abs(top_y - current_y) > (line_height * 0.5):
            # New line detected (using 50% of line height as threshold)
            if current_line:
                # Sort current line by X coordinate (left to right) to preserve reading order
                current_line.sort(key=lambda x: x[0][0][0])
                line_text = " ".join([item[1] for item in current_line])
                lines.append(line_text)
            current_line = [(bbox, text)]
            current_y = top_y
        else:
            # Same line, add to current line
            current_line.append((bbox, text))
    
    # Add last line
    if current_line:
        current_line.sort(key=lambda x: x[0][0][0])
        line_text = " ".join([item[1] for item in current_line])
        lines.append(line_text)
    
    return "\n".join(lines)


def reset_easyocr_reader():
    """
    Manually reset the EasyOCR reader to prevent quality degradation.
    Call this if you notice OCR quality decreasing over time.
    """
    global _reader, _reader_initialized, _read_count
    if _reader is not None:
        try:
            del _reader
        except:
            pass
    _reader = None
    _reader_initialized = False
    _read_count = 0
    print("EasyOCR reader has been reset")


if __name__ == "__main__":
    img = "product_page.png"
    t1 = ocr_pytesseract(img)
    t2 = ocr_easyocr(img)
    print("----- pytesseract -----\n", t1[:1000])
    print("----- easyocr -----\n", t2[:1000])

