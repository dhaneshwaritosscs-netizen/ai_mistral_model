import os
import json
import re
import time
import webbrowser
from capture import capture_fullpage
from ocr import ocr_easyocr, ocr_pytesseract
from scrape_dom import fetch_dom_text, fetch_dom_with_playwright
from call_model_hf import call_hf_inference, extract_json_from_response

# Prompt template for review extraction
REVIEW_PROMPT_TEMPLATE = """Extract rating, ratings count, reviews count, and customer review from the FULL extracted text (may contain OCR errors).

EXTRACTION RULES (search ENTIRE text, handle OCR errors):
1. Rating: Find rating number (4, 4.3, 4.4, 3.5, 4.2) that appears:
   - BEFORE or AFTER star symbols (★, ⭐, ☆, *) - can be "4★" or "★4" or "4.3★"
   - Near "out of 5 stars" or "stars" text
   - Can be single digit with star: "4★", "4 ★", "★4"
   - Can be decimal: "4.3", "4 3", "4-3" (OCR may split decimal)
   - Rating range: 0.0 to 5.0
   - Look for numbers 0-5 near star symbols or ratings section

2. Ratings Count: Find number before "Ratings" or "ratings" text:
   - Pattern: "NUMBER Ratings" (e.g., "7,624 ratings", "7624 ratings", "7 624 ratings")
   - Remove commas and spaces: "7,624" → 7624
   - Look for large numbers (hundreds or thousands) near "ratings"

3. Reviews Count: Find number before "Reviews" or "reviews" text:
   - Pattern: "NUMBER Reviews" (e.g., "140 reviews", "205 reviews")
   - Can also be part of "NUMBER ratings and NUMBER reviews"

4. Review: Find customer review text:
   - Look after "reviews", "customer review", "verified purchase", customer names
   - Extract FIRST meaningful review sentence/paragraph
   - Clean OCR errors but preserve meaning
   - If no review text, use null

OUTPUT JSON:
{{"rating": <decimal_or_null>, "ratings_count": <integer_or_null>, "reviews_count": <integer_or_null>, "review": "<text_or_null>", "source": "ocr"}}

SPECIAL HANDLING:
- OCR text may have errors: "4 3" might be "4.3", "7624" might be "7 624" or "7,624"
- Search for variations: "out of 5", "stars", "ratings", "reviews"
- For Amazon: look for "4.3 out of 5 stars" and "7,624 ratings"
- Extract ANY numbers that look like ratings/reviews counts even if text is garbled

Examples:
Input: "Panasonic\n4.3 out of 5 stars\n7,624 ratings\nCustomer review: Excellent product."
Output: {{"rating": 4.3, "ratings_count": 7624, "reviews_count": null, "review": "Excellent product.", "source": "ocr"}}

Input: "Aroma\n4★\n3,34,015 Ratings & 17,504 Reviews\nProduct features"
Output: {{"rating": 4.0, "ratings_count": 334015, "reviews_count": 17504, "review": null, "source": "ocr"}}

Input: "4 3 stars\n7624 ratings\n140 reviews\nGreat quality monitor"
Output: {{"rating": 4.3, "ratings_count": 7624, "reviews_count": 140, "review": "Great quality monitor", "source": "ocr"}}

Input: "Price 6440\nProduct features\nNo ratings visible"
Output: {{"rating": null, "ratings_count": null, "reviews_count": null, "review": null, "source": "ocr"}}

Now extract from this FULL text (may have OCR errors):
{input_text}
"""

def run(url, use_dom_first=True, use_ocr_fallback=True):
    """
    Run the complete pipeline: capture page, extract text, and get review/rating.
    """
    extracted_text = ""
    source = "unknown"
    
    # Try to extract rating from DOM attributes (for Flipkart/visual stars)
    dom_rating = None
    if use_dom_first:
        try:
            from scrape_dom import extract_rating_from_dom
            dom_rating = extract_rating_from_dom(url)
            if dom_rating:
                print(f"Found rating {dom_rating} from DOM attributes")
        except Exception as e:
            print(f"DOM rating extraction failed: {e}")
    
    # Try DOM extraction first
    if use_dom_first:
        try:
            print("Attempting DOM extraction...")
            extracted_text = fetch_dom_text(url)
            source = "dom"
            if len(extracted_text.strip()) < 50:
                print("DOM text too short, trying Playwright...")
                extracted_text = fetch_dom_with_playwright(url)
                source = "dom"
            
            # If rating found in DOM, prepend it
            if dom_rating:
                extracted_text = f"Rating: {dom_rating} stars\n{extracted_text}"
        except Exception as e:
            print(f"DOM extraction failed: {e}")
            use_ocr_fallback = True
    
    # OCR fallback
    if use_ocr_fallback or len(extracted_text.strip()) < 50:
        try:
            print("Attempting OCR extraction...")
            img_path = capture_fullpage(url, out_path="tmp_page.png")
            
            # Try EasyOCR first
            extracted_text = ocr_easyocr(img_path, lang_list=['en'], force_reset=False)
            source = "ocr"
            easyocr_length = len(extracted_text.strip())
            print(f"EasyOCR extracted {easyocr_length} characters")
            
            # If EasyOCR gives short result, try pytesseract and combine
            if easyocr_length < 100:
                print("EasyOCR text too short, trying pytesseract...")
                tesseract_text = ocr_pytesseract(img_path, aggressive=False)
                tesseract_length = len(tesseract_text.strip())
                print(f"pytesseract extracted {tesseract_length} characters")
                
                # Use the longer result, or combine if both are decent
                if tesseract_length > easyocr_length:
                    extracted_text = tesseract_text
                elif tesseract_length > 50:
                    # Combine both results
                    extracted_text = f"{extracted_text}\n{tesseract_text}"
            
            source = "ocr"
        except Exception as e:
            print(f"OCR extraction failed: {e}")
            import traceback
            traceback.print_exc()
            if len(extracted_text.strip()) < 50:
                return {"rating": None, "ratings_count": None, "reviews_count": None, "review": None, "source": source, "error": str(e)}
    
    if len(extracted_text.strip()) < 10:
        return {"rating": None, "ratings_count": None, "reviews_count": None, "review": None, "source": source, "error": "Insufficient text extracted"}
    
    # Debug print
    print(f"\nExtracted {len(extracted_text)} characters of text")
    print("Preview (first 1500 chars):")
    print(extracted_text[:1500])
    print("\nPreview (middle section - ratings/reviews usually here):")
    if len(extracted_text) > 2000:
        mid_start = len(extracted_text) // 3
        print(extracted_text[mid_start:mid_start+800])
    print("\nPreview (last 500 chars):")
    if len(extracted_text) > 500:
        print(extracted_text[-500:])
    print("...\n")

    # Regex-based fallback extraction
    fallback_rating = dom_rating if dom_rating else None
    fallback_ratings_count = None
    fallback_reviews_count = None
    
    # Find rating patterns
    rating_patterns = [
        r'(\d+\.?\d*)\s*(?:out\s+of\s+5|stars?|★|⭐|☆)',
        r'(\d+)\s*(?:★|⭐|☆)',
        r'(\d+\.?\d*)\s*(?:ou\s+or|out\s+of)\s*5',
        r'(\d+)\s*\.\s*(\d+)\s*(?:stars?|★|⭐)',
        r'\b([0-5])\s*(?:★|⭐|☆)',
        r'(\b[0-5](?:\.\d)?)\s*\n?\s*(?=\d{2,}\s*Ratings)',
        r'(\b[0-5])\s+(?=\d{3,}\s*Ratings)',
    ]
    
    ratings_line_match = re.search(r'(\b[0-5](?:\.\d)?)\s*.*?(\d{3,})\s*Ratings', extracted_text, re.IGNORECASE)
    if ratings_line_match and not fallback_rating:
        rating_candidate = float(ratings_line_match.group(1))
        if 0 <= rating_candidate <= 5:
            fallback_rating = rating_candidate
    
    product_rating_match = re.search(r'\)\s*(\b[0-5](?:\.\d)?)\s*\n\s*(\d{3,})\s*Ratings', extracted_text, re.IGNORECASE)
    if product_rating_match and not fallback_rating:
        rating_candidate = float(product_rating_match.group(1))
        if 0 <= rating_candidate <= 5:
            fallback_rating = rating_candidate
    
    if not fallback_rating:
        lines = extracted_text.split('\n')
        for i, line in enumerate(lines):
            if 'ratings' in line.lower():
                check_lines = lines[max(0, i-3):i+1]
                for check_line in check_lines:
                    decimal_match = re.search(r'(?<!\d)([0-5](?:\.\d{1,2})?)(?!\d)', check_line)
                    if decimal_match:
                        rating_val = float(decimal_match.group(1))
                        if 0 <= rating_val <= 5:
                            if not re.search(rf'{rating_val}\s*ratings?', check_line, re.IGNORECASE):
                                fallback_rating = rating_val
                                break
                if fallback_rating:
                    break
    if not fallback_rating:
        for pattern in rating_patterns:
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    try:
                        num1 = int(match.group(1))
                        num2 = int(match.group(2))
                        if num1 <= 5 and num2 <= 9:
                            fallback_rating = float(f"{num1}.{num2}")
                        else:
                            fallback_rating = float(match.group(1))
                    except:
                        fallback_rating = float(match.group(1))
                else:
                    rating_val = float(match.group(1))
                    if 0 < rating_val <= 5:
                        fallback_rating = rating_val
                if fallback_rating and fallback_rating > 5:
                    fallback_rating = None
                if fallback_rating:
                    break
    
    ratings_patterns = [
        r'(\d{1,2}(?:[,\.]\d{2})*(?:[,\.]\d{3})*)\s*rat(?:in|ir)?g?s?\b',
        r'(\d{1,3}(?:[,\.]\d{3})*)\s*rat(?:in|ir)?g?s?\b',
        r'(\d{2,})\s*rat(?:in|ir)?g?s?\b',
    ]
    for pattern in ratings_patterns:
        ratings_match = re.search(pattern, extracted_text, re.IGNORECASE)
        if ratings_match:
            num_str = ratings_match.group(1).replace(',', '').replace('.', '').replace(' ', '')
            if num_str.isdigit() and len(num_str) >= 2:
                fallback_ratings_count = int(num_str)
                break
    
    reviews_patterns = [
        r'(\d{1,2}(?:[,\.]\d{2})*(?:[,\.]\d{3})*)\s*reviews?\b',
        r'(\d{1,3}(?:[,\.]\d{3})*)\s*reviews?\b',
        r'(\d{1,})\s*reviews?\b',
    ]
    for pattern in reviews_patterns:
        reviews_match = re.search(pattern, extracted_text, re.IGNORECASE)
        if reviews_match:
            num_str = reviews_match.group(1).replace(',', '').replace('.', '').replace(' ', '')
            if num_str.isdigit():
                fallback_reviews_count = int(num_str)
                break
    
    # Use more text for better extraction (increased limits)
    # Only truncate if text is very long to avoid API limits
    if len(extracted_text) > 12000:
        if "amazon" in url.lower():
            text_to_use = extracted_text[:10000]  # Increased from 8000
        else:
            text_to_use = extracted_text[:8000]  # Increased from 6000
        print(f"Text truncated to {len(text_to_use)} characters (original: {len(extracted_text)})")
    else:
        text_to_use = extracted_text
        print(f"Using full text ({len(text_to_use)} characters)")
    
    prompt = REVIEW_PROMPT_TEMPLATE.format(input_text=text_to_use)
    
    try:
        api_key = os.environ.get("HF_TOKEN") or os.environ.get("MISTRAL_API_KEY")
        use_mistral = api_key and not api_key.startswith("hf_")
        
        if use_mistral:
            print("Calling Mistral API...")
        else:
            print("Calling Hugging Face model...")
        
        out = call_hf_inference(prompt, use_mistral_api=use_mistral)
        model_txt = extract_json_from_response(out, is_mistral=use_mistral)
        
        print(f"\nModel response preview (first 500 chars):")
        print(model_txt[:500])
        print("...\n")
        
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', model_txt, re.S)
        if code_block_match:
            json_match = code_block_match.group(1)
        else:
            json_match = re.search(r'\{[^{}]*"rating"[^{}]*"review"[^{}]*"source"[^{}]*\}', model_txt, re.S)
            if not json_match:
                json_match = re.search(r'\{.*?"rating".*?\}', model_txt, re.S)
            else:
                json_match = json_match.group(0)
        
        if json_match:
            try:
                json_str = json_match if isinstance(json_match, str) else json_match.group(0)
                j = json.loads(json_str)
                
                if isinstance(j.get("review"), list):
                    review_list = j["review"]
                    j["review"] = " ".join(str(r) for r in review_list if r) if review_list else None
                
                if isinstance(j.get("rating"), str):
                    num_match = re.search(r'(\d+\.?\d*)', str(j["rating"]))
                    if num_match:
                        j["rating"] = float(num_match.group(1))
                        if j["rating"] > 5:
                            j["rating"] = j["rating"] / 10
                    else:
                        j["rating"] = None
                elif j.get("rating") is not None:
                    j["rating"] = float(j["rating"])
                    if j["rating"] > 5:
                        j["rating"] = None
                
                if "ratings_count" in j:
                    if isinstance(j["ratings_count"], str):
                        count_str = j["ratings_count"].replace(",", "").replace(" ", "")
                        num_match = re.search(r'(\d+)', count_str)
                        j["ratings_count"] = int(num_match.group(1)) if num_match else None
                    elif j["ratings_count"] is not None:
                        j["ratings_count"] = int(j["ratings_count"])
                
                if "reviews_count" in j:
                    if isinstance(j["reviews_count"], str):
                        count_str = j["reviews_count"].replace(",", "").replace(" ", "")
                        num_match = re.search(r'(\d+)', count_str)
                        j["reviews_count"] = int(num_match.group(1)) if num_match else None
                    elif j["reviews_count"] is not None:
                        j["reviews_count"] = int(j["reviews_count"])
                
                j["source"] = source
                
                if j.get("rating") is None and fallback_rating:
                    j["rating"] = fallback_rating
                if j.get("ratings_count") is None and fallback_ratings_count:
                    j["ratings_count"] = fallback_ratings_count
                if j.get("reviews_count") is None and fallback_reviews_count:
                    j["reviews_count"] = fallback_reviews_count
                
                return j
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        
        if fallback_rating or fallback_ratings_count or fallback_reviews_count:
            return {
                "rating": fallback_rating,
                "ratings_count": fallback_ratings_count,
                "reviews_count": fallback_reviews_count,
                "review": None,
                "source": source,
                "note": "Extracted using regex fallback (API parsing failed)"
            }
        
        return {"rating": None, "ratings_count": None, "reviews_count": None, "review": None, "source": source, "error": "Could not parse model output"}
    except Exception as e:
        print(f"Model call failed: {e}")
        return {"rating": None, "review": None, "source": source, "error": str(e)}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.meesho.com/example-product-url"
    
    print(f"Processing URL: {url}")

    # ---------- NEW: Open URL in Chrome so you can see it ----------
    try:
        # Try to open in Chrome; fallback to default browser
        webbrowser.get("chrome").open(url)
    except:
        webbrowser.open(url)
    time.sleep(3)  # Pause a bit so you can see the page
    # ---------------------------------------------------------------
    
    res = run(url)
    print("\n" + "="*50)
    print("RESULT:")
    print("="*50)
    print(json.dumps(res, indent=2))
