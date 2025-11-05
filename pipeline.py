import os
import json
import re
from capture import capture_fullpage
from ocr import ocr_easyocr, ocr_pytesseract
from scrape_dom import fetch_dom_text, fetch_dom_with_playwright
from call_model_hf import call_hf_inference, extract_json_from_response

# Load config automatically (if not already set)
try:
    from config import setup_environment
    setup_environment()
except ImportError:
    pass  # config.py might not exist in older versions

# Field definitions - describes how to extract each field
FIELD_DEFINITIONS = {
    "rating": {
        "description": "Product rating (0.0 to 5.0)",
        "rules": [
            "Find rating number (4, 4.3, 4.4, 3.5, 4.2) that appears:",
            "- BEFORE or AFTER star symbols (★, ⭐, ☆, *) - can be '4★' or '★4' or '4.3★'",
            "- Near 'out of 5 stars' or 'stars' text",
            "- Can be single digit with star: '4★', '4 ★', '★4'",
            "- Can be decimal: '4.3', '4 3', '4-3' (OCR may split decimal)",
            "- CRITICAL: Read rating EXACTLY - if you see '4' stars, extract exactly '4.0' or '4', not '40' or '0.4'",
            "- If you see '4.0' or '4', both are valid - read exactly as shown",
            "- OCR may split: '4 0' should be read as '4.0' (if decimal context) or '4' (if whole number)",
            "- Rating range: 0.0 to 5.0 - read exactly, no mistakes",
            "- Look for numbers 0-5 near star symbols or ratings section",
            "- Read each digit carefully: '4.3' not '43' or '4.30' (unless shown)"
        ],
        "type": "decimal",
        "example": "4.3"
    },
    "ratings_count": {
        "description": "Total number of ratings",
        "rules": [
            "Find number before 'Ratings' or 'ratings' text:",
            "- Pattern: 'NUMBER Ratings' (e.g., '7,624 ratings', '7624 ratings', '7 624 ratings')",
            "- CRITICAL: Read numerical values EXACTLY - NO mistakes",
            "- OCR may split numbers: '7624' might appear as '7 624' or '76 24' - read as '7624'",
            "- OCR may have spaces in numbers: '26 Ratings' → exactly '26', not '2 6' or '260'",
            "- Remove commas and spaces: '7,624' → exactly 7624 (not 762 or 76240)",
            "- Read each digit carefully before 'ratings' text",
            "- Look for large numbers (hundreds or thousands) near 'ratings'",
            "- Handle Indian number format: '3,34,015' → exactly 334015"
        ],
        "type": "integer",
        "example": 7624
    },
    "reviews_count": {
        "description": "Total number of reviews",
        "rules": [
            "Find number before 'Reviews' or 'reviews' text:",
            "- Pattern: 'NUMBER Reviews' (e.g., '140 reviews', '205 reviews')",
            "- Can also be part of 'NUMBER ratings and NUMBER reviews'",
            "- Handle Indian number format: '17,504' → 17504"
        ],
        "type": "integer",
        "example": 140
    },
    "review": {
        "description": "Customer review text",
        "rules": [
            "Find customer review text:",
            "- Look after 'reviews', 'customer review', 'verified purchase', customer names",
            "- Extract FIRST meaningful review sentence/paragraph",
            "- Clean OCR errors but preserve meaning",
            "- If no review text, use null"
        ],
        "type": "string",
        "example": "Great quality product, arrived on time."
    },
    # "price": {
    #     "description": "Product price in rupees or currency",
    #     "rules": [
    #         "Find product price:",
    #         "- IMPORTANT: If price is struck-through (crossed out), it is NOT the current price - it is MRP. Skip struck-through prices.",
    #         "- Look for currency symbols: ₹, Rs, Rs., $, etc.",
    #         "- Patterns: '₹299', 'Rs. 299', '₹1,299', 'Rs 1299', 'Price: ₹299'",
    #         "- Can be: '₹2,999' or 'Rs. 2999' or '2,999' (without symbol)",
    #         "- Handle Indian number format with commas",
    #         "- Extract the main/current price (NOT struck-through, NOT old price, NOT MRP)",
    #         "- CRITICAL: Read numerical values EXACTLY - if text shows '₹874', extract EXACTLY '₹874', NOT '₹3874' or '₹7498'",
    #         "- REAL EXAMPLE: If screenshot shows '₹874' as the current price, the price field MUST be '₹874'. Extracting '₹3874' means you added an extra '3' digit - that is WRONG.",
    #         "- OCR may split numbers: '874' might appear as '8 74', '87 4', or '8 7 4' - ALL should be read as '874'",
    #         "- OCR may MISREAD digits: '874' might be incorrectly read as '3874' (adding extra '3') - VERIFY digit count!",
    #         "- Read each digit CAREFULLY one by one: If text shows '₹874', count: first digit is '8', second is '7', third is '4' = exactly '874'",
    #         "- Common OCR errors to avoid: '874' might be misread as '3874' (extra '3' at start - WRONG) or '7498' (completely wrong digits - WRONG)",
    #         "- If text shows '₹874' as current price (not struck-through), extract EXACTLY '₹874' - 3 digits, no more, no less",
    #         "- Handle commas: If you see '₹874' (no comma), extract '₹874'. Don't add extra digits like '3' before '874'.",
    #         "- VERIFICATION RULE: Before returning price, count digits - '874' = 3 digits (8-7-4). If you have '3874' = 4 digits, you added an extra digit - that is an ERROR!",
    #         "- Remove currency symbol and return as number or string ",
    #     ],
    #     "type": "string",
    #     "example": "₹299"
    # },
    "price": {
  "description": "Extract the current (non-crossed-out) selling price of the product.",
  "rules": [
    "1. Look for currency values with symbols like ₹, Rs, Rs., $, etc.",
    "2. If a price is struck-through (crossed out), IGNORE it — it is MRP or old price.",
    "3. The non-crossed-out price shown near 'Special price', 'Offer price', or discount text is the CURRENT price.",
    "4. CRITICAL: Read digits EXACTLY as shown - if you see '₹592', extract EXACTLY '₹592' (3 digits: 5-9-2), NOT '₹202' or any other value.",
    "5. CRITICAL: Count digits carefully - '₹592' has 3 digits (5, 9, 2). If you extract '₹202', that is WRONG (digits are 2, 0, 2 which don't match 5, 9, 2).",
    "6. OCR may split numbers: '592' might appear as '5 92', '59 2', or '5 9 2' - ALL should be read as EXACTLY '592'.",
    "7. OCR may MISREAD digits: '592' might be incorrectly read as '202' (5→2, 9→0) or '442' (5→4, 9→4) - VERIFY each digit carefully!",
    "8. Read each digit ONE BY ONE: If text shows '₹592', count: first digit is '5', second is '9', third is '2' = exactly '₹592'.",
    "9. Extract the value exactly as displayed, including the currency symbol (e.g., '₹592').",
    "10. If multiple prices exist, pick the one that is highlighted, largest, or next to 'Special price'.",
    "11. Do not change digits or symbols — keep commas and currency symbol as shown.",
    "12. VERIFICATION: Before returning, verify digits match what you see - '₹592' = digits 5-9-2, NOT 2-0-2 or 4-4-2.",
    "13. Return only one value — the current price."
  ],
  "type": "string",
  "example": "₹592"
},
"mrp": {
  "description": "Extract the MRP or original price that is crossed out (struck-through).",
  "rules": [
    "1. CRITICAL: MRP is the STRUCK-THROUGH (crossed-out) price that appears NEAR the current price - NOT from ratings/reviews section.",
    "2. CRITICAL: DO NOT extract numbers from 'ratings' or 'reviews' text - those are NOT MRP. Example: '2,82,519 ratings' is NOT MRP, ignore it.",
    "3. CRITICAL: MRP appears in the PRICING SECTION, usually right above or next to the current price (₹592), NOT in the ratings area.",
    "4. Look for prices with currency symbols like ₹, Rs, Rs., $, etc. that appear NEAR the current price.",
    "5. Identify the price that is struck-through (crossed out) - this is the MRP. It appears near 'Special price' or discount text.",
    "6. CRITICAL: Read digits EXACTLY as shown - if you see '₹1,302' or '₹1302' NEAR the current price ₹592, extract EXACTLY '₹1,302' (4 digits: 1-3-0-2), NOT '2,825' or any other number.",
    "7. CRITICAL: If you see '2,82,519' or '2,825' near 'ratings' or 'reviews' text, that is NOT MRP - ignore it completely!",
    "8. CRITICAL: MRP should be close to the price value - if current price is ₹592, MRP should be nearby (like ₹1,302), NOT far away in ratings section.",
    "9. CRITICAL: Count digits carefully - '₹1,302' has 4 digits (1, 3, 0, 2). If you extract '2,825' (from ratings), that is WRONG - that's not MRP!",
    "10. OCR may split numbers: '1302' might appear as '1 302', '13 02', '1 3 0 2' - ALL should be read as EXACTLY '1302' or '1,302'.",
    "11. OCR may MISREAD digits: '1,302' might be incorrectly read as '442' (1→4, 3→4, 0→2, 2 missing) - VERIFY each digit carefully!",
    "12. Read each digit ONE BY ONE: If text shows '₹1,302', count: first digit is '1', second is '3', third is '0', fourth is '2' = exactly '₹1,302'.",
    "13. Extract that value exactly as shown, including the currency symbol (e.g., '₹1,302').",
    "14. If multiple crossed-out prices exist, choose the one appearing NEAREST to the current price or discount percentage.",
    "15. Do not extract any price that is not crossed-out.",
    "16. DO NOT extract numbers from these sections: ratings, reviews, offers (unless it's clearly a price), delivery charges.",
    "17. Preserve commas and currency symbols as displayed.",
    "18. VERIFICATION: Before returning, verify: (a) digits match what you see - '₹1,302' = digits 1-3-0-2, (b) it's NOT from ratings/reviews section, (c) it appears near the current price."
  ],
  "type": "string",
  "example": "₹1,302"
},

    "product_name": {
        "description": "Product name or title",
        "rules": [
            "Find product name/title:",
            "- Usually appears at the top of the page",
            "- May be in headings (h1, h2) or prominent text",
            "- Extract the main product title, clean OCR errors",
            "- Skip generic text like 'Home', 'Shop', etc."
        ],
        "type": "string",
        "example": "Men's Cotton T-Shirt"
    },
    "discount": {
        "description": "Discount percentage or amount",
        "rules": [
            "Find discount information:",
            "- Look for '% off', 'discount', 'save', 'off'",
            "- Patterns: '20% off', 'Save 20%', '₹100 off', '20% discount'",
            "- Extract percentage or amount",
            "- Return as string or number"
        ],
        "type": "string",
        "example": "20% off"
    },
    "availability": {
        "description": "Product availability status",
        "rules": [
            "Find availability status:",
            "- Look for: 'In Stock', 'Out of Stock', 'Available', 'Unavailable'",
            "- May appear near price or add to cart button",
            "- Extract status text"
        ],
        "type": "string",
        "example": "In Stock"
    }
}

def generate_prompt_template(fields):
    """
    Generate a dynamic prompt template based on requested fields.
    Supports both predefined fields and custom field names.
    
    Args:
        fields: List of field names to extract (e.g., ['price', 'rating', 'M.R.P.'])
    
    Returns:
        str: Prompt template string
    """
    if not fields:
        fields = ["rating", "review"]  # Default
    
    # Build extraction rules for each field
    rules_text = ""
    valid_fields = set(FIELD_DEFINITIONS.keys())
    
    for i, field in enumerate(fields, 1):
        if field in FIELD_DEFINITIONS:
            # Predefined field with detailed rules
            field_def = FIELD_DEFINITIONS[field]
            rules_text += f"\n{i}. {field_def['description'].replace('Product ', '')} ({field}):\n"
            for rule in field_def["rules"]:
                rules_text += f"   {rule}\n"
        else:
            # Custom field - use more comprehensive extraction rules
            # Normalize field name for display (replace dots/spaces with readable format)
            display_name = field.replace("_", " ").replace(".", " ").strip()
            field_lower = field.lower()
            display_lower = display_name.lower()
            
            # Handle multi-word field names like "Operating System"
            field_parts = display_name.split()
            field_without_spaces = display_name.replace(" ", "")
            field_with_dash = display_name.replace(" ", "-")
            field_with_underscore = field.replace("-", "_")
            
            rules_text += f"\n{i}. Extract {display_name} ({field}):\n"
            rules_text += f"   - Search the ENTIRE text thoroughly for '{display_name}' (with space) or '{field}' (without space)\n"
            rules_text += f"   - Also search for variations: '{field_with_dash}', '{field_without_spaces}', '{field_with_underscore}'\n"
            rules_text += f"   - IMPORTANT: OCR may join words together - search for '{display_name.replace(' ', '')}' (no space) too\n"
            rules_text += f"   - For '{display_name}', also search for each word separately: "
            for idx, part in enumerate(field_parts):
                rules_text += f"'{part}'"
                if idx < len(field_parts) - 1:
                    rules_text += " and "
            rules_text += f" appearing near each other\n"
            rules_text += f"   - CRITICAL: Read the text LINE BY LINE - if you see '{display_name}' (or variations) on line N:\n"
            rules_text += f"     * Start extracting from line N (same line) OR line N+1 (next line) OR line N+2, N+3 (nearby lines)\n"
            rules_text += f"     * Extract ALL content/data related to '{display_name}' by reading line by line\n"
            rules_text += f"     * KEEP READING and extracting until you see:\n"
            rules_text += f"       - A DIFFERENT field/title/section header (like 'Delivery Option', 'Brand', 'Price', 'ADD TO BAG', etc.)\n"
            rules_text += f"       - A new major section that is clearly NOT part of '{display_name}'\n"
            rules_text += f"     * Extract EVERYTHING under '{display_name}' until the next section/title appears\n"
            rules_text += f"   - Look for patterns like:\n"
            rules_text += f"     * '{display_name}: VALUE' (e.g., 'Operating System: Android 15')\n"
            rules_text += f"     * '{display_name} VALUE' (e.g., 'Operating System Android 15')\n"
            rules_text += f"     * '{display_name}- VALUE' or '{display_name} - VALUE'\n"
            rules_text += f"     * '{display_name}' on one line, then multiple lines of values/content\n"
            rules_text += f"     * '{display_name.replace(' ', '')}' (no space) followed by values on same or next line\n"
            rules_text += f"   - For UI elements like buttons/dropdowns (e.g., 'SELECT SIZE'):\n"
            rules_text += f"     * If you see '{display_name}' or '{display_name.replace(' ', '')}' (or parts like 'SELECT' and 'SIZE'), look for size options\n"
            rules_text += f"     * Size options appear as: single letters 'S', 'M', 'L' or combinations 'XL', 'XXL', 'XXXL'\n"
            rules_text += f"     * Sizes might be on the SAME line as '{display_name}' OR on the NEXT 1-5 lines\n"
            rules_text += f"     * Example: If you see 'SELECT SIZE' or 'SELECTSIZE' followed by 'S S S M L XL XXL' anywhere nearby, extract ALL: 'S S S M L XL XXL'\n"
            rules_text += f"     * Example: If you see 'SELECT SIZE S M L XL' on same line, extract 'S M L XL'\n"
            rules_text += f"     * Keep reading lines after '{display_name}' until you hit another field/title (like 'ADD TO BAG', 'Delivery Option', 'Brand', etc.)\n"
            rules_text += f"     * Extract COMPLETE data - don't stop at first item, extract ALL items until next section\n"
            rules_text += f"     * If you find '{display_name}' but cannot find any size options (S, M, L, XL, XXL) nearby, still return what you find or null\n"
            if len(field_parts) > 1:
                # For multi-word fields, also search for each word separately
                rules_text += f"   - For '{display_name}', also check if words appear together: "
                for idx, part in enumerate(field_parts):
                    rules_text += f"'{part}'"
                    if idx < len(field_parts) - 1:
                        rules_text += " followed by "
                rules_text += f"\n"
            rules_text += f"   - Handle OCR errors where spaces might be missing or added\n"
            rules_text += f"   - Look in: product specifications, details section, 'About this item', description, features, UI buttons, dropdowns, anywhere\n"
            rules_text += f"   - MOST IMPORTANT: Extract ALL content under '{display_name}' until you hit another field/title\n"
            rules_text += f"     * Example: '{display_name}' on line 50, then 'S M L XL' on lines 51-52, then 'Delivery Option' on line 53\n"
            rules_text += f"       → Extract 'S M L XL' (everything from line 50 to line 52, stop at line 53 where new section starts)\n"
            rules_text += f"     * Example: '{display_name}' on line 50, then 'S S S M L XL XXL' on line 51, then 'Brand' on line 52\n"
            rules_text += f"       → Extract 'S S S M L XL XXL' (all sizes, stop at 'Brand' which is next section)\n"
            rules_text += f"     * Example: 'SELECTSIZE' (no space) on line 50, then 'S M L XL XXL' on line 51, then 'ADD TO BAG' on line 52\n"
            rules_text += f"       → Extract 'S M L XL XXL' (all sizes, stop at 'ADD TO BAG' which is next section)\n"
            rules_text += f"     * Example: 'SELECT SIZE S M L XL XXL' all on same line 50, then 'WISHLIST' on line 51\n"
            rules_text += f"       → Extract 'S M L XL XXL' (sizes from same line, stop at 'WISHLIST' which is next section)\n"
            rules_text += f"   - Extract the COMPLETE value/content - extract ALL items, options, or text until next section\n"
            rules_text += f"   - Examples for '{display_name}':\n"
            rules_text += f"     * If text says '{display_name}: Android 15', extract 'Android 15' (full value)\n"
            rules_text += f"     * If text says '{display_name}' on line 50, then 'S S S M L XL XXL' on line 51, then 'Delivery' on line 52\n"
            rules_text += f"       → Extract 'S S S M L XL XXL' (all sizes, stop when 'Delivery' section starts)\n"
            rules_text += f"     * If text says '{display_name}' but no content follows (next line has another field), extract null\n"
            rules_text += f"   - If field name has spaces like '{display_name}', OCR might have 'OperatingSystem' or 'Operating System' - check both\n"
            rules_text += f"   - Extract FULL value even if it's long (like offers, descriptions, etc.) - don't truncate\n"
            rules_text += f"   - NO LIMIT on value length - extract complete information - do NOT stop in middle\n"
            rules_text += f"   - For long text fields like 'Available offers': Extract ALL text until next section/title appears\n"
            rules_text += f"   - If value continues across lines, keep reading until you hit another field/title/section\n"
            rules_text += f"   - Do NOT cut off text in middle - extract EVERYTHING until the next section starts\n"
            rules_text += f"   - Example: 'Available offers: Bank Offer...' followed by more offers, then 'Delivery Option: ...'\n"
            rules_text += f"     → Extract ALL offers text until 'Delivery Option' appears (that's the next section)\n"
            rules_text += f"   - Return this field in JSON output - do NOT skip any custom fields\n"
            rules_text += f"   - If you find '{display_name}' but the next line immediately has another field/title, return null\n"
    
    # Build output JSON structure (escape braces for format())
    # IMPORTANT: NO LIMIT on number of fields - extract ALL requested fields
    output_json_parts = []
    valid_fields = set(FIELD_DEFINITIONS.keys())
    
    for field in fields:
        if field in FIELD_DEFINITIONS:
            # Predefined field - use known type
            field_def = FIELD_DEFINITIONS[field]
            if field_def["type"] == "decimal":
                output_json_parts.append(f'"{field}": <decimal_or_null>')
            elif field_def["type"] == "integer":
                output_json_parts.append(f'"{field}": <integer_or_null>')
            else:
                output_json_parts.append(f'"{field}": "<text_or_null>"')
        else:
            # Custom field - default to string (can be number or text)
            # NO LIMIT - extract as many custom fields as requested
            output_json_parts.append(f'"{field}": "<value_or_null>"')
    
    # Escape braces in JSON structure
    # Include ALL fields (predefined + custom) - no limit
    output_json_str = "{{" + ", ".join(output_json_parts) + ', "source": "ocr"}}'
    
    # Build examples (properly escape all braces)
    examples_text = "\nExamples:\n"
    
    # Add example for SELECT SIZE if it's in the fields
    if any(f.lower() in ["select size", "selectsize", "size"] for f in fields):
        examples_text += """Input: "SELECT SIZE\nS M L XL XXL\nADD TO BAG"
Output: {{"SELECT SIZE": "S M L XL XXL", "source": "ocr"}}

Input: "SELECTSIZE S S S M L XL XXL\nWISHLIST"
Output: {{"SELECT SIZE": "S S S M L XL XXL", "source": "ocr"}}

"""
    
    if "price" in fields and "mrp" in fields:
        examples_text += """Input: "Product Name\nSpecial price: ₹592\n₹1,302 (crossed out)\n54% off\n4.2★\n2,82,519 ratings"
Output: {{"price": "₹592", "mrp": "₹1,302", "source": "ocr"}}
NOTE: MRP is ₹1,302 (the crossed-out price), NOT 2,82,519 (that's ratings count - ignore it!)

Input: "Product Name\nPrice: ₹299\nRating: 4.3"
Output: {{"price": "₹299", "mrp": null, "rating": 4.3, "source": "ocr"}}

"""
    elif "price" in fields:
        examples_text += """Input: "Product Name\nPrice: ₹299\nRating: 4.3"
Output: {{"price": "₹299", "rating": 4.3, "source": "ocr"}}

"""
    if "rating" in fields and "price" not in fields:
        examples_text += """Input: "Panasonic\n4.3 out of 5 stars\n7,624 ratings"
Output: {{"rating": 4.3, "ratings_count": 7624, "source": "ocr"}}

"""
    
    # Build prompt template - escape all JSON braces
    prompt = """Extract the following information from the FULL extracted text (may contain OCR errors).

CRITICAL INSTRUCTIONS - READ LINE BY LINE:
1. The text below is extracted LINE BY LINE from a screenshot - read it EXACTLY as it appears
2. Read each line sequentially from top to bottom, DO NOT skip any lines
3. IMPORTANT: There is NO LIMIT on the number of fields to extract - extract ALL requested fields
4. For EACH field (including all custom fields), scan through ALL lines one by one
5. CRITICAL: When you find a field name (e.g., "SELECT SIZE"), extract ALL content/data under that field
6. Keep reading line by line after finding the field name and extract EVERYTHING until you see:
   - A DIFFERENT field/title/section header (like "Delivery Option", "Brand", "Price", etc.)
   - A new major section that is clearly NOT part of the current field
7. Examples:
   - "SELECT SIZE" on line 50, then "S S S M L XL XXL" on line 51, then "Delivery Option" on line 52
     → Extract "S S S M L XL XXL" (all sizes, stop at "Delivery Option" which is next section)
   - "SELECTSIZE" (no space) on line 50, then "S M L XL XXL" on line 51, then "ADD TO BAG" on line 52
     → Extract "S M L XL XXL" (all sizes, stop at "ADD TO BAG" which is next section)
   - "SELECT SIZE S M L XL" all on same line 50, then "WISHLIST" on line 51
     → Extract "S M L XL" (all sizes from same line, stop at "WISHLIST" which is next section)
   - "Available offers:" on line 50, then multiple lines of offers, then "Brand:" on line 60
     → Extract ALL offers from line 50 to line 59, stop at "Brand:" which is next section
8. Look for patterns like:
   - Line N: "Operating System: Android 15"  → Extract "Android 15"
   - Line N: "SELECT SIZE" followed by Line N+1: "S S S M L XL XXL" → Extract "S S S M L XL XXL"
   - Line N: "Brand Nothing"  → Extract "Nothing"
9. Read line by line - if a field name appears on line 50, extract from line 50 onwards until next section
10. Extract the COMPLETE value/content - extract ALL items/options until next section/title appears
11. Check specifications sections, "About this item", product details, offers section - READ LINE BY LINE
12. Extract ALL custom fields - there is NO limit on how many custom attributes you can extract

EXTRACTION RULES (read LINE BY LINE, handle OCR errors):{rules_text}

OUTPUT JSON:
{output_json}

CRITICAL OUTPUT REQUIREMENTS:
- You MUST return ALL requested fields in the JSON output - NO fields should be missing
- There is ABSOLUTELY NO LIMIT on the number of custom fields - extract ALL of them
- If 10 custom fields are requested, return all 10. If 50 are requested, return all 50. If 100 are requested, return all 100.
- Each custom field must have its entry in the JSON: "field_name": "value" or "field_name": null
- Do NOT skip any custom fields - extract every single one that was requested
- MOST CRITICAL: For each field, extract ALL content/data until you see another field/title/section
- Example for "SELECT SIZE": If you see "SELECT SIZE" followed by "S S S M L XL XXL", then "Delivery Option"
  → Extract "S S S M L XL XXL" (all sizes, stop when "Delivery Option" appears - that's the next section)
- Example for "Available offers": Extract ALL offers text until you see another field/title (like "Brand", "Price", etc.)
- Do NOT stop extracting in the middle - extract EVERYTHING under the field until the next section starts
- If field value spans multiple lines, read ALL lines and extract everything until next section/title
- For "SELECT SIZE" or similar UI fields: Extract ALL available options (S M L XL XXL, etc.) until next section
- For "Available offers", "Services", or similar fields: Extract ALL offers/services until next field/title appears
- Do NOT stop at first period, semicolon, or first item - keep reading until you hit another section/title

SPECIAL HANDLING - LINE BY LINE READING:
- Read the text EXACTLY as it appears line by line from the screenshot
- CRITICAL: Read ALL numerical values EXACTLY as they appear - NO MISTAKES in numbers
- MOST IMPORTANT FOR PRICE/MRP: Count digits carefully - if you see "₹592", it has EXACTLY 3 digits (5, 9, 2). Do NOT read it as "₹202" (wrong digits 2-0-2) or "₹442" (wrong digits 4-4-2).
- MOST IMPORTANT FOR PRICE/MRP: If you see "₹1,302" or "₹1302", it has EXACTLY 4 digits (1, 3, 0, 2). Do NOT read it as "₹442" (wrong digits 4-4-2) or "2,825" (from ratings - NOT MRP!).
- CRITICAL FOR MRP: MRP is the STRUCK-THROUGH price NEAR the current price - NOT from ratings section. If you see "2,82,519 ratings", that number "2,82,519" is NOT MRP - ignore it!
- EXAMPLE FROM REAL DATA: If text shows "₹592" as price, extract EXACTLY "₹592" (digits: 5-9-2). If you extract "₹202" (digits: 2-0-2), that is WRONG - you misread 5 as 2 and 9 as 0.
- EXAMPLE FROM REAL DATA: If text shows "₹1,302" as MRP (crossed-out near ₹592), extract EXACTLY "₹1,302" (digits: 1-3-0-2). If you extract "2,825" from "2,82,519 ratings", that is WRONG - that's not MRP, that's ratings count!
- CRITICAL: MRP appears in pricing section near current price. Numbers in "ratings", "reviews", "offers" sections are NOT MRP - ignore them!
- OCR text may have errors: numbers may be split by spaces
  * "5 9 2" should be read as "592" (remove spaces between digits)
  * "1 3 0 2" should be read as "1302" or "1,302" (remove spaces, keep comma if present)
  * "592" might appear as "5 92", "59 2", or "5 9 2" - ALL should be read as EXACTLY "592"
  * "1302" might appear as "1 302", "13 02", or "1 3 0 2" - ALL should be read as EXACTLY "1302" or "1,302"
  * "4 3" should be read as "4.3" (if decimal context) or "43" (if rating like 4 stars)
  * "7624" might appear as "7 624" or "76 24" - read it as EXACTLY "7624"
- OCR may MISREAD digits: "592" might be incorrectly read as "202" (5→2, 9→0) or "442" (5→4, 9→4) - CHECK CAREFULLY
- OCR may MISREAD digits: "1,302" might be incorrectly read as "442" (1→4, 3→4, 0→2, 2 missing) - VERIFY each digit ONE BY ONE
- Read each digit carefully - if text shows "₹592", extract EXACTLY "592" (3 digits: 5-9-2), NOT "202" (2-0-2) or "442" (4-4-2)
- Read each digit carefully - if text shows "₹1,302", extract EXACTLY "1,302" (4 digits: 1-3-0-2), NOT "442" (4-4-2) or any other value
- Handle commas in numbers: "1,302" = keep as "1,302" or "1302" (both valid), "22,011" = "22,011" or "22011"
- For decimal numbers: "4.0" or "4.3" - read exactly as shown, not "40" or "43"
- VERIFY: Before returning price/MRP, count the digits and verify:
  * "₹592" = 3 digits (5, 9, 2) - if you have different digits, you made an error!
  * "₹1,302" = 4 digits (1, 3, 0, 2) - if you have "₹442" (3 digits: 4, 4, 2), you made an error!
- For price and MRP: If a price is struck-through (crossed out), it is MRP, NOT the current price
- Current price is the one that is NOT struck-through. Struck-through price = MRP.
- DOUBLE CHECK: After extracting price/MRP, verify the digits match what you see in the text. If digits don't match, you misread them - try again!
- Field values appear on the SAME LINE as field name OR on the NEXT LINES until another section/title appears
- CRITICAL: For each field, extract ALL content/data by reading line by line until you hit another field/title/section
- Example: If line 25 says "SELECT SIZE", then extract from line 25 onwards until you see another field (like "Delivery Option" on line 27)
  → Extract everything from line 25 to line 26 (all sizes/options), stop at line 27 where new section starts
- For UI elements like buttons/dropdowns (e.g., "SELECT SIZE"): Extract ALL options/values shown until next section
  * "SELECT SIZE" on line 50, "S S S M L XL XXL" on line 51, "Delivery Option" on line 52
  → Extract "S S S M L XL XXL" (all sizes, stop at "Delivery Option")
- For multi-word fields: "Operating System" might appear as "OperatingSystem" or "Operating  System"
- Common patterns (read line by line):
  * Line: "Brand: Nothing" → Extract "Nothing"  
  * Line: "Brand" followed by next line: "Nothing" → Extract "Nothing"
  * Line: "Operating System: Android 15" → Extract "Android 15"
  * Line: "SELECT SIZE" or "SELECTSIZE" followed by "S S S M L XL XXL", then "Delivery Option" or "ADD TO BAG" → Extract "S S S M L XL XXL" (all sizes)
  * Line: "SELECT SIZE S M L XL XXL" on same line → Extract "S M L XL XXL" (all sizes from same line)
  * Price: If "₹592" (normal) and "₹1,302" (struck-through) → price="₹592", mrp="₹1,302"
  * CRITICAL: If you see "₹592" and "2,82,519 ratings" - price="₹592", mrp="₹1,302" (the crossed-out one), NOT "2,82,519" (that's ratings count, not MRP!)
  * Numbers: "26 Ratings" → exactly "26" (for ratings_count), "4 stars" → exactly "4" or "4.0" (for rating)
  * MRP: Look for struck-through price NEAR current price, NOT in ratings section
- Read through ALL lines systematically - don't jump around
- If field name is on line N, start extracting from line N and keep reading until you see another field/title/section
- IMPORTANT: If you find a field name but the next line immediately has another field/title, return null (field exists but no content)
- Read the text below LINE BY LINE exactly as it appears from the screenshot
- DOUBLE CHECK all numbers before returning - one digit mistake is not acceptable!
- For ALL fields (including custom fields): Extract ALL content under the field until you see another field/title/section

{examples_text}
Now extract from this FULL text (read LINE BY LINE exactly as shown, may have OCR errors):
{input_text}
""".format(
        rules_text=rules_text,
        output_json=output_json_str,
        examples_text=examples_text,
        input_text="{input_text}"  # This will be replaced by the caller
    )
    return prompt

def run(url, fields=None, use_dom_first=True, use_ocr_fallback=True):
    """
    Run the complete pipeline: capture page, extract text, and get specified fields.
    
    Args:
        url: The product page URL to process
        fields: List of fields to extract (e.g., ['price'], ['rating', 'review'], ['price', 'rating', 'product_name'])
                Available fields: rating, ratings_count, reviews_count, review, price, product_name, discount, availability
                If None, defaults to ['rating', 'review']
        use_dom_first: Try DOM extraction first (more accurate)
        use_ocr_fallback: Use OCR if DOM fails or as fallback
    
    Returns:
        dict: Extracted data with only the requested fields + source
    """
    # Set default fields if not provided
    if fields is None:
        fields = ["rating", "review"]
    elif isinstance(fields, str):
        # If single string, convert to list
        fields = [fields]
    
    # Field aliases - map common variations to standard field names
    FIELD_ALIASES = {
        "m.r.p.": "mrp",
        "mrp": "mrp",
        "maximum retail price": "mrp",
        "list price": "mrp",
        "original price": "mrp"
    }
    
    # Normalize field names (convert to lowercase, strip spaces)
    normalized_fields = []
    for field in fields:
        field_lower = field.lower().strip()
        # Check if it's an alias
        if field_lower in FIELD_ALIASES:
            normalized_fields.append(FIELD_ALIASES[field_lower])
        else:
            # Keep original case for custom fields, but check predefined fields case-insensitively
            valid_fields_lower = {k.lower(): k for k in FIELD_DEFINITIONS.keys()}
            if field_lower in valid_fields_lower:
                normalized_fields.append(valid_fields_lower[field_lower])
            else:
                # Custom field - keep original
                normalized_fields.append(field)
    
    fields = normalized_fields
    
    # Separate predefined and custom fields
    valid_fields = set(FIELD_DEFINITIONS.keys())
    predefined_fields = [f for f in fields if f in valid_fields]
    custom_fields = [f for f in fields if f not in valid_fields]
    
    if custom_fields:
        print(f"Note: Custom fields detected: {custom_fields}")
        print(f"These will be extracted using generic rules.")
    
    if not fields:
        fields = ["rating", "review"]  # Fallback to default
    extracted_text = ""
    source = "unknown"
    img_path = None
    
    # ALWAYS capture screenshot for every URL (user requirement)
    print("Capturing screenshot...")
    try:
        img_path = capture_fullpage(url, out_path="tmp_page.png")
        print(f"Screenshot saved to: {img_path}")
    except Exception as e:
        print(f"Warning: Screenshot capture failed: {e}")
        # Continue anyway, will try to use DOM or retry screenshot later
    
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
    
    # Try DOM extraction first (more accurate)
    if use_dom_first:
        try:
            print("Attempting DOM extraction...")
            extracted_text = fetch_dom_text(url)
            source = "dom"
            if len(extracted_text.strip()) < 50:
                print("DOM text too short, trying Playwright...")
                extracted_text = fetch_dom_with_playwright(url)
                source = "dom"
            
            # If we found rating in DOM, prepend it to extracted text
            if dom_rating:
                extracted_text = f"Rating: {dom_rating} stars\n{extracted_text}"
            
        except Exception as e:
            print(f"DOM extraction failed: {e}")
            use_ocr_fallback = True
    
    # OCR fallback or if DOM text is insufficient
    if use_ocr_fallback or len(extracted_text.strip()) < 50:
        try:
            print("Attempting OCR extraction...")
            # If screenshot wasn't captured earlier, try again
            if img_path is None:
                try:
                    img_path = capture_fullpage(url, out_path="tmp_page.png")
                    print(f"Screenshot saved to: {img_path}")
                except Exception as e:
                    print(f"OCR screenshot capture failed: {e}")
                    if len(extracted_text.strip()) < 50:
                        error_result = {f: None for f in fields}
                        error_result["source"] = source
                        error_result["error"] = f"Screenshot capture failed: {str(e)}"
                        return error_result
            
            if img_path:
                # Try both OCR methods and combine for maximum text extraction
                print("Extracting text with EasyOCR...")
                easyocr_text = ocr_easyocr(img_path, lang_list=['en'])
                print(f"EasyOCR extracted {len(easyocr_text)} characters")
                
                print("Extracting text with pytesseract...")
                tesseract_text = ocr_pytesseract(img_path)
                print(f"pytesseract extracted {len(tesseract_text)} characters")
                
                # Combine both results to get ALL text
                # Use the longer one as base, and add unique content from the other
                if len(easyocr_text) > len(tesseract_text):
                    extracted_text = easyocr_text
                    # Add any unique lines from tesseract
                    easyocr_lines = set(easyocr_text.split('\n'))
                    tesseract_lines = tesseract_text.split('\n')
                    for line in tesseract_lines:
                        if line.strip() and line.strip() not in easyocr_lines:
                            extracted_text += "\n" + line
                else:
                    extracted_text = tesseract_text
                    # Add any unique lines from easyocr
                    tesseract_lines = set(tesseract_text.split('\n'))
                    easyocr_lines = easyocr_text.split('\n')
                    for line in easyocr_lines:
                        if line.strip() and line.strip() not in tesseract_lines:
                            extracted_text += "\n" + line
                
                source = "ocr"
                print(f"Combined OCR extracted {len(extracted_text)} characters total")
                
                # Fallback if combined text is still too short
                if len(extracted_text.strip()) < 50:
                    print("Warning: Combined OCR text is too short, using longer one individually...")
                    if len(easyocr_text.strip()) > len(tesseract_text.strip()):
                        extracted_text = easyocr_text
                    else:
                        extracted_text = tesseract_text
        except Exception as e:
            print(f"OCR extraction failed: {e}")
            if len(extracted_text.strip()) < 50:
                error_result = {f: None for f in fields}
                error_result["source"] = source
                error_result["error"] = str(e)
                return error_result
    
    if len(extracted_text.strip()) < 10:
        error_result = {f: None for f in fields}
        error_result["source"] = source
        error_result["error"] = "Insufficient text extracted"
        return error_result
    
    # Debug: print FULL extracted text (complete text from screenshot)
    # Also show line-by-line structure
    lines = extracted_text.split('\n')
    print(f"\n{'='*60}")
    print(f"FULL EXTRACTED TEXT FROM SCREENSHOT ({len(extracted_text)} characters, {len(lines)} lines):")
    print(f"{'='*60}")
    # Print with line numbers for better debugging
    for idx, line in enumerate(lines[:100], 1):  # Show first 100 lines
        print(f"Line {idx:3d}: {line}")
    if len(lines) > 100:
        print(f"... ({len(lines) - 100} more lines) ...")
    print(f"{'='*60}")
    print(f"END OF EXTRACTED TEXT\n")
    
    # Try to extract rating/numbers using regex as fallback (before API call)
    import re
    # Start with DOM-extracted rating if available
    fallback_rating = dom_rating if dom_rating else None
    fallback_ratings_count = None
    fallback_reviews_count = None
    
    # Try to find rating: decimal number near "stars" or "out of 5"
    # Also handle cases like "4★" or "4 ★" (single digit with star symbol)
    # Also look for single digit (0-5) that appears before ratings count (not part of count)
    rating_patterns = [
        r'(\d+\.?\d*)\s*(?:out\s+of\s+5|stars?|★|⭐|☆)',  # "4.3 stars" or "4★"
        r'(\d+)\s*(?:★|⭐|☆)',  # "4★" or "4 ★" (single digit with star)
        r'(\d+\.?\d*)\s*(?:ou\s+or|out\s+of)\s*5',
        r'(\d+)\s*\.\s*(\d+)\s*(?:stars?|★|⭐)',
        r'\b([0-5])\s*(?:★|⭐|☆)',  # "4★" pattern (single digit 0-5 with star)
        # Try to find rating before ratings count - look for single digit (0-5) on same line or before large number
        r'(\b[0-5](?:\.\d)?)\s*\n?\s*(?=\d{2,}\s*Ratings)',  # "4" or "4.3" followed by large number and "Ratings"
        # Pattern: single digit 0-5 that appears before ratings text (context-based)
        r'(\b[0-5])\s+(?=\d{3,}\s*Ratings)',  # "4" followed by large number (3+ digits) and "Ratings"
    ]
    
    # Also check if there's a pattern like "4" near "Ratings" text (rating might be on same line)
    # Look for small number (0-5) near "Ratings" but not part of the count
    # This pattern looks for rating before/after Ratings count (e.g., "4.2 3,34,015 Ratings")
    ratings_line_match = re.search(r'(\b[0-5](?:\.\d)?)\s*.*?(\d{3,})\s*Ratings', extracted_text, re.IGNORECASE)
    if ratings_line_match and not fallback_rating:
        rating_candidate = float(ratings_line_match.group(1))
        if 0 <= rating_candidate <= 5:
            fallback_rating = rating_candidate
    
    # Also try reverse: look for rating after product name but before large numbers
    # Pattern: product text, then rating (0-5), then ratings count
    product_rating_match = re.search(r'\)\s*(\b[0-5](?:\.\d)?)\s*\n\s*(\d{3,})\s*Ratings', extracted_text, re.IGNORECASE)
    if product_rating_match and not fallback_rating:
        rating_candidate = float(product_rating_match.group(1))
        if 0 <= rating_candidate <= 5:
            fallback_rating = rating_candidate
    
    # Last resort: look for any decimal number 0-5 that appears on lines near "Ratings"
    # Extract lines around "Ratings" and check for rating pattern
    if not fallback_rating:
        lines = extracted_text.split('\n')
        for i, line in enumerate(lines):
            if 'ratings' in line.lower() or ('ratings' in line.lower() and 'reviews' in line.lower()):
                # Check previous 3 lines and current line for rating
                check_lines = lines[max(0, i-3):i+1]
                for check_line in check_lines:
                    # Look for decimal number 0-5 - be more flexible
                    # Try pattern: "4" or "4.2" that's not part of a larger number
                    decimal_match = re.search(r'(?<!\d)([0-5](?:\.\d{1,2})?)(?!\d)', check_line)
                    if decimal_match:
                        rating_val = float(decimal_match.group(1))
                        # Make sure it's not part of ratings count (should be < 6 and on a different part of line)
                        if 0 <= rating_val <= 5:
                            # Check if this number is NOT immediately before "ratings" (that would be count)
                            if not re.search(rf'{rating_val}\s*ratings?', check_line, re.IGNORECASE):
                                fallback_rating = rating_val
                                break
                if fallback_rating:
                    break
    # Only try regex patterns if we don't already have a DOM-extracted rating
    if not fallback_rating:
        for pattern in rating_patterns:
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    try:
                        num1 = int(match.group(1))
                        num2 = int(match.group(2))
                        if num1 <= 5 and num2 <= 9:  # Valid rating format (e.g., 4.3)
                            fallback_rating = float(f"{num1}.{num2}")
                        else:
                            fallback_rating = float(match.group(1))
                    except:
                        fallback_rating = float(match.group(1))
                else:
                    rating_val = float(match.group(1))
                    # Handle single digit ratings (like "4★")
                    # Skip 0.0 as it's likely not a real rating
                    if 0 < rating_val <= 5:
                        fallback_rating = rating_val
                    else:
                        continue  # Skip if invalid
                if fallback_rating and fallback_rating > 5:
                    fallback_rating = None
                if fallback_rating:
                    break
    
    # Try to find ratings count: number before "ratings"
    # Handle Indian number format: "3,34,015" (comma after 3 digits, then 2 digits)
    ratings_patterns = [
        r'(\d{1,2}(?:[,\.]\d{2})*(?:[,\.]\d{3})*)\s*rat(?:in|ir)?g?s?\b',  # "3,34,015 Ratings" (Indian format)
        r'(\d{1,3}(?:[,\.]\d{3})*)\s*rat(?:in|ir)?g?s?\b',  # "7,624 ratings" (standard format)
        r'(\d{2,})\s*rat(?:in|ir)?g?s?\b',  # "7624 ratings"
    ]
    for pattern in ratings_patterns:
        ratings_match = re.search(pattern, extracted_text, re.IGNORECASE)
        if ratings_match:
            num_str = ratings_match.group(1).replace(',', '').replace('.', '').replace(' ', '')
            if num_str.isdigit() and len(num_str) >= 2:  # At least 2 digits (likely a count)
                fallback_ratings_count = int(num_str)
                break
    
    # Try to find reviews count: number before "reviews"
    # Handle Indian number format: "17,504" 
    reviews_patterns = [
        r'(\d{1,2}(?:[,\.]\d{2})*(?:[,\.]\d{3})*)\s*reviews?\b',  # "17,504 Reviews" (Indian format)
        r'(\d{1,3}(?:[,\.]\d{3})*)\s*reviews?\b',  # "140 reviews" (standard format)
        r'(\d{1,})\s*reviews?\b',
    ]
    for pattern in reviews_patterns:
        reviews_match = re.search(pattern, extracted_text, re.IGNORECASE)
        if reviews_match:
            num_str = reviews_match.group(1).replace(',', '').replace('.', '').replace(' ', '')
            if num_str.isdigit():
                fallback_reviews_count = int(num_str)
                break
    
    # Generate dynamic prompt based on requested fields
    prompt_template = generate_prompt_template(fields)
    
    # Compose prompt - ALWAYS use FULL text to extract all data
    # IMPORTANT: Never truncate text - use everything extracted from screenshot
    # This ensures we capture ALL fields that might appear anywhere in the text
    has_custom_fields = any(f not in FIELD_DEFINITIONS for f in fields)
    
    # ALWAYS use FULL extracted text - no truncation ever
    # This is critical to ensure we don't miss any fields
    text_to_use = extracted_text
    total_lines = len(text_to_use.split('\n'))
    print(f"Using FULL extracted text ({len(text_to_use)} characters) - NO TRUNCATION")
    print(f"Total lines in extracted text: {total_lines}")
    
    # Replace the placeholder with actual text
    prompt = prompt_template.replace("{input_text}", text_to_use)
    
    # Call model
    try:
        # Ensure token is loaded before making API call
        try:
            from config import setup_environment
            setup_environment()
        except ImportError:
            pass
        
        # Detect if we should use Mistral API based on token format
        import os
        api_key = os.environ.get("HF_TOKEN") or os.environ.get("MISTRAL_API_KEY")
        use_mistral = api_key and not api_key.startswith("hf_")
        
        if use_mistral:
            print("Calling Mistral API...")
        else:
            print("Calling Hugging Face model...")
        
        out = call_hf_inference(prompt, use_mistral_api=use_mistral)
        model_txt = extract_json_from_response(out, is_mistral=use_mistral)
        
        # Debug: print FULL model response
        print(f"\n{'='*60}")
        print("FULL MODEL RESPONSE:")
        print(f"{'='*60}")
        print(model_txt)
        print(f"{'='*60}\n")
        
        # Extract JSON from model output
        # Strategy 1: Extract from markdown code blocks (preferred)
        code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?)\s*```', model_txt, re.S)
        if code_block_match:
            json_match = code_block_match.group(1)
        else:
            # Strategy 2: Find JSON starting from first { and find matching closing }
            start_idx = model_txt.find('{')
            if start_idx != -1:
                # Count braces to find matching closing brace
                brace_count = 0
                json_end = -1
                for i in range(start_idx, len(model_txt)):
                    if model_txt[i] == '{':
                        brace_count += 1
                    elif model_txt[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i
                            break
                
                if json_end > start_idx:
                    json_match = model_txt[start_idx:json_end+1]
                else:
                    # If no matching brace, try to find last } or extract what we can
                    json_match = re.search(r'\{[\s\S]{50,}', model_txt)  # At least 50 chars
                    if json_match:
                        json_match = json_match.group(0)
                    else:
                        json_match = None
            else:
                # Strategy 3: Regex fallback
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', model_txt, re.S)
                if json_match:
                    json_match = json_match.group(0)
                else:
                    json_match = None
        
        result = {}
        
        if json_match:
            try:
                # json_match might be a string or a match object
                json_str = json_match if isinstance(json_match, str) else json_match.group(0)
                
                # Try to fix incomplete JSON that might be cut off
                # If JSON seems incomplete (missing closing brace), try to complete it
                json_str = json_str.strip()
                
                # Count braces
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                
                # If incomplete, try to fix
                if open_braces > close_braces:
                    # Missing closing braces - try to complete
                    missing_braces = open_braces - close_braces
                    # Try to find where to close - look for last complete key-value pair
                    # Add closing braces before the last quote or after last comma
                    if json_str.rstrip().endswith(','):
                        json_str = json_str.rstrip().rstrip(',')
                    json_str += '}' * missing_braces
                
                # Remove trailing commas before closing braces/brackets
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                
                # Try parsing
                j = json.loads(json_str)
                print(f"✅ Successfully parsed JSON with {len(j)} fields")
                
                # Validate and clean each requested field based on its type
                # IMPORTANT: Process ALL fields (no limit) - ensure every requested field is included
                valid_fields_set = set(FIELD_DEFINITIONS.keys())
                print(f"Processing {len(fields)} requested fields (including {len([f for f in fields if f not in valid_fields_set])} custom fields)")
                
                for field in fields:
                    if field in j:
                        field_def = FIELD_DEFINITIONS.get(field, {})
                        field_type = field_def.get("type", "string") if field in valid_fields_set else "string"
                        value = j[field]
                        
                        if field_type == "decimal":
                            # Validate decimal (for rating)
                            if isinstance(value, str):
                                num_match = re.search(r'(\d+\.?\d*)', str(value))
                                if num_match:
                                    value = float(num_match.group(1))
                                    if value > 5 and field == "rating":
                                        value = value / 10 if value > 5 else value
                                    if value > 5:
                                        value = None
                                else:
                                    value = None
                            elif value is not None:
                                value = float(value)
                                if value > 5 and field == "rating":
                                    value = None
                        elif field_type == "integer":
                            # Validate integer (for counts)
                            if isinstance(value, str):
                                count_str = value.replace(",", "").replace(" ", "").replace(".", "")
                                num_match = re.search(r'(\d+)', count_str)
                                value = int(num_match.group(1)) if num_match else None
                            elif value is not None:
                                value = int(value)
                        elif field == "review":
                            # Ensure review is a string, not an array
                            if isinstance(value, list):
                                value = " ".join(str(r) for r in value if r) if value else None
                            else:
                                value = str(value) if value else None
                        else:
                            # String fields (including custom fields) - keep as string, but try to preserve format
                            # IMPORTANT: For long custom fields like "Available offers", keep COMPLETE value
                            if isinstance(value, list):
                                # Join list items but preserve complete text
                                value = " ".join(str(r) for r in value if r) if value else None
                            else:
                                # Keep complete string value - don't truncate
                                value = str(value) if value else None
                                # Log if value seems truncated (ends with incomplete sentence)
                                if value and len(value) > 100 and not value.rstrip().endswith(('.', '!', '?', ';', 'T&C')):
                                    print(f"Warning: Field '{field}' value might be truncated (ends with: ...{value[-50:]})")
                        
                        # Special validation for price and MRP
                        if field == "price" or field == "mrp":
                            if value and isinstance(value, str):
                                # Extract numeric value for validation
                                # Remove currency symbols and commas
                                numeric_str = re.sub(r'[₹Rs\s,$]', '', str(value))
                                # Remove any non-digit characters except decimal point
                                numeric_str = re.sub(r'[^\d.]', '', numeric_str)
                                if numeric_str:
                                    try:
                                        numeric_value = float(numeric_str)
                                        # Log the extracted value for debugging
                                        print(f"Extracted {field}: '{value}' (numeric: {numeric_value})")
                                        
                                        # Special validation for MRP - check if it looks like ratings count
                                        if field == "mrp":
                                            # If MRP is very large (>10000) or looks suspicious, warn
                                            if numeric_value > 10000:
                                                print(f"⚠️  Warning: MRP value {numeric_value} seems unusually high. This might be from ratings section, not actual MRP!")
                                            # Check if value looks like it could be ratings count (e.g., 2,82,519 -> 282519)
                                            if numeric_value > 1000 and numeric_value < 1000000:
                                                # Check extracted text for context clues
                                                if "ratings" in extracted_text.lower() or "reviews" in extracted_text.lower():
                                                    # Try to find ratings count in text
                                                    ratings_match = re.search(r'(\d{1,2}(?:[,\.]\d{2})*(?:[,\.]\d{3})*)\s*rat(?:in|ir)?g?s?\b', extracted_text, re.IGNORECASE)
                                                    if ratings_match:
                                                        ratings_num_str = ratings_match.group(1).replace(',', '').replace('.', '').replace(' ', '')
                                                        if ratings_num_str.isdigit():
                                                            ratings_num = int(ratings_num_str)
                                                            # If MRP is close to ratings count, it's probably wrong
                                                            if abs(numeric_value - ratings_num) < 1000:
                                                                print(f"⚠️  Warning: MRP value {numeric_value} is very close to ratings count {ratings_num}. This is likely incorrect - MRP should be near the price, not from ratings section!")
                                    except:
                                        print(f"Warning: Could not parse {field} value '{value}' as number")
                        
                        result[field] = value
                    else:
                        result[field] = None
                
                # Cross-validate price and MRP
                if "price" in result and "mrp" in result:
                    price_val = result.get("price")
                    mrp_val = result.get("mrp")
                    
                    if price_val and mrp_val:
                        # Extract numeric values
                        price_num = None
                        mrp_num = None
                        
                        if isinstance(price_val, str):
                            price_str = re.sub(r'[₹Rs\s,$]', '', str(price_val))
                            price_str = re.sub(r'[^\d.]', '', price_str)
                            if price_str:
                                try:
                                    price_num = float(price_str)
                                except:
                                    pass
                        
                        if isinstance(mrp_val, str):
                            mrp_str = re.sub(r'[₹Rs\s,$]', '', str(mrp_val))
                            mrp_str = re.sub(r'[^\d.]', '', mrp_str)
                            if mrp_str:
                                try:
                                    mrp_num = float(mrp_str)
                                except:
                                    pass
                        
                        # Validate: MRP should be >= price (usually)
                        if price_num and mrp_num:
                            if mrp_num < price_num:
                                print(f"⚠️  Warning: MRP ({mrp_num}) is less than price ({price_num}). This might be incorrect.")
                            else:
                                print(f"✅ Price/MRP validation: Price={price_num}, MRP={mrp_num} (MRP >= Price)")
                
                result["source"] = source
                
                # Use fallback values if API returned nulls but we found something with regex/DOM
                if "rating" in fields and result.get("rating") is None and fallback_rating:
                    result["rating"] = fallback_rating
                if "ratings_count" in fields and result.get("ratings_count") is None and fallback_ratings_count:
                    result["ratings_count"] = fallback_ratings_count
                if "reviews_count" in fields and result.get("reviews_count") is None and fallback_reviews_count:
                    result["reviews_count"] = fallback_reviews_count
                
                # Filter to only return requested fields + source
                # IMPORTANT: Return ALL requested fields - no limit
                filtered_result = {f: result.get(f) for f in fields}
                filtered_result["source"] = result.get("source", source)
                
                # Verify all fields are present
                missing_fields = [f for f in fields if f not in filtered_result]
                if missing_fields:
                    print(f"Warning: Some fields missing from result: {missing_fields}")
                    for f in missing_fields:
                        filtered_result[f] = None
                
                print(f"Returning {len(filtered_result)} fields in result")
                return filtered_result
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        
        # Fallback: use regex-extracted values if available for requested fields
        fallback_result = {"source": source, "note": "Extracted using regex fallback (API parsing failed)"}
        if "rating" in fields and fallback_rating:
            fallback_result["rating"] = fallback_rating
        if "ratings_count" in fields and fallback_ratings_count:
            fallback_result["ratings_count"] = fallback_ratings_count
        if "reviews_count" in fields and fallback_reviews_count:
            fallback_result["reviews_count"] = fallback_reviews_count
        
        # Initialize null values for other requested fields
        for field in fields:
            if field not in fallback_result:
                fallback_result[field] = None
        
        # Only return if we have at least one non-null value
        if any(v is not None for k, v in fallback_result.items() if k not in ["source", "note"]):
            # Filter to only requested fields
            filtered = {f: fallback_result.get(f) for f in fields}
            filtered["source"] = source
            if "note" in fallback_result:
                filtered["note"] = fallback_result["note"]
            return filtered
        
        # Final fallback: return nulls for all requested fields
        # IMPORTANT: Return ALL requested fields even if parsing failed - no limit
        final_result = {f: None for f in fields}
        final_result["source"] = source
        final_result["error"] = "Could not parse model output"
        print(f"Final fallback: Returning {len(final_result)} fields (all requested fields with null values)")
        return final_result
    except Exception as e:
        print(f"Model call failed: {e}")
        error_result = {f: None for f in fields}
        error_result["source"] = source
        error_result["error"] = str(e)
        return error_result

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.meesho.com/example-product-url"  # replace with actual URL
    
    # Parse fields from command line arguments
    fields = None
    if len(sys.argv) > 2:
        # Check if second argument is --fields or comma-separated
        if sys.argv[2].startswith("--fields="):
            fields_str = sys.argv[2].split("=", 1)[1]
            fields = [f.strip() for f in fields_str.split(",")]
        elif sys.argv[2] == "--fields" and len(sys.argv) > 3:
            fields = [f.strip() for f in sys.argv[3].split(",")]
        else:
            # Treat remaining arguments as field names (space-separated)
            fields = [f.strip() for f in sys.argv[2:]]
    
    if fields:
        print(f"Extracting fields: {', '.join(fields)}")
        valid_fields_set = set(FIELD_DEFINITIONS.keys())
        predefined = [f for f in fields if f in valid_fields_set]
        custom = [f for f in fields if f not in valid_fields_set]
        if predefined:
            print(f"Predefined fields: {', '.join(predefined)}")
        if custom:
            print(f"Custom fields: {', '.join(custom)}")
    
    print(f"Processing URL: {url}")
    res = run(url, fields=fields)
    print("\n" + "="*50)
    print("RESULT:")
    print("="*50)
    print(json.dumps(res, indent=2))

