# 📋 Project Flow aur Code Explanation (हिंदी/English)

## 🎯 Project Overview
Yeh ek **Product Data Extraction System** hai jo product pages se structured data extract karta hai using AI.

---

## 📁 Files aur Unka Kaam

### 1. **app.py** - Flask Web Server (Main Entry Point)
**Kaam:**
- Flask web server start karta hai
- User ko web interface provide karta hai
- API endpoints expose karta hai

**Key Functions:**
- `@app.route('/')` - Homepage render karta hai
- `@app.route('/api/extract', methods=['POST'])` - Product URL se data extract karta hai
- `@app.route('/api/fields', methods=['GET'])` - Available fields list return karta hai

**Flow:**
```
User → Web Form → /api/extract → pipeline.run() → Response JSON
```

---

### 2. **pipeline.py** - Main Processing Logic (सबसे Important)
**Kaam:**
- Complete extraction pipeline ko handle karta hai
- Screenshot capture → Text extraction → AI model call → JSON parsing

**Key Functions:**

#### `run(url, fields=None)`
Main function jo complete flow ko handle karta hai:

**Step-by-Step Flow:**
1. **Screenshot Capture:**
   ```python
   img_path = capture_fullpage(url, out_path="tmp_page.png")
   ```
   - Playwright use karke full page screenshot leta hai

2. **Text Extraction (2 methods):**
   - **DOM Extraction (First Try):**
     ```python
     extracted_text = fetch_dom_text(url)  # BeautifulSoup
     # OR
     extracted_text = fetch_dom_with_playwright(url)  # JS-rendered content
     ```
   - **OCR Fallback:**
     ```python
     easyocr_text = ocr_easyocr(img_path)
     tesseract_text = ocr_pytesseract(img_path)
     # Combine both results
     ```

3. **AI Model Call:**
   ```python
   prompt = generate_prompt_template(fields)  # Dynamic prompt banata hai
   out = call_hf_inference(prompt)  # Model ko call karta hai
   model_txt = extract_json_from_response(out)
   ```

4. **JSON Parsing:**
   - Model response se JSON extract karta hai
   - Field validation aur type conversion karta hai
   - Fallback values use karta hai (regex-extracted)

#### `generate_prompt_template(fields)`
- Requested fields ke liye dynamic prompt banata hai
- Predefined fields (rating, price, etc.) aur custom fields dono support karta hai
- Detailed extraction rules add karta hai

**Predefined Fields:**
- `rating` - Product rating (0.0 to 5.0)
- `ratings_count` - Total ratings count
- `reviews_count` - Total reviews count
- `review` - Customer review text
- `price` - Current price
- `product_name` - Product title
- `discount` - Discount percentage
- `availability` - Stock status
- `mrp` - Maximum Retail Price

---

### 3. **capture.py** - Screenshot Capture
**Kaam:**
- Playwright use karke web pages ka screenshot leta hai
- Anti-bot detection techniques use karta hai

**Key Functions:**

#### `capture_fullpage(url, out_path)`
- Main function jo screenshot capture karta hai
- Site-specific handling (Amazon, Flipkart, Myntra, etc.)
- Anti-bot detection bypass techniques:
  - User agent spoofing
  - Webdriver property removal
  - Realistic browser context
  - Extra headers

#### `_capture_myntra(url, out_path)`
- Myntra ke liye special handling (strong bot detection)
- Multiple strategies try karta hai:
  1. Mobile user agent
  2. Chromium stealth mode
  3. Non-headless browser
  4. Firefox browser
  5. Alternative Chromium settings

---

### 4. **ocr.py** - Text Extraction from Images
**Kaam:**
- Screenshot images se text extract karta hai
- 2 OCR engines use karta hai: EasyOCR aur pytesseract

**Key Functions:**

#### `ocr_easyocr(image_path)`
- EasyOCR use karta hai (better for mixed fonts)
- Line-by-line structure preserve karta hai
- Bounding boxes se text ordering maintain karta hai

#### `ocr_pytesseract(image_path)`
- Tesseract OCR use karta hai
- Simpler but faster
- Line structure preserve karta hai

**Why Both?**
- EasyOCR: Better accuracy, mixed fonts handle karta hai
- Tesseract: Faster, simpler text
- Combine karke maximum text extraction

---

### 5. **scrape_dom.py** - DOM Text Extraction
**Kaam:**
- HTML DOM se directly text extract karta hai
- JavaScript-rendered content handle karta hai

**Key Functions:**

#### `fetch_dom_text(url)`
- BeautifulSoup use karke simple HTML parse karta hai
- Fast but JavaScript content miss ho sakta hai

#### `fetch_dom_with_playwright(url)`
- Playwright use karke JS-rendered content handle karta hai
- Networkidle wait karta hai (dynamic content load hone ke liye)

#### `extract_rating_from_dom(url)`
- DOM attributes se rating directly extract karta hai
- Flipkart/Amazon ke liye specific selectors use karta hai

---

### 6. **call_model_hf.py** - AI Model Integration
**Kaam:**
- HuggingFace Inference API aur Mistral API ko call karta hai
- Model se structured data extract karta hai

**Key Functions:**

#### `call_hf_inference(prompt, use_mistral_api=False)`
- HuggingFace API call karta hai
- Retry logic with exponential backoff
- Token authentication handle karta hai

#### `call_mistral_api(prompt)`
- Mistral API directly call karta hai
- Rate limit handling
- Timeout handling for large prompts

#### `extract_json_from_response(resp, is_mistral=False)`
- API response se generated text extract karta hai
- Different response formats handle karta hai

**Model Used:**
- Default: `mistralai/Mistral-7B-Instruct-v0.2`
- Mistral API: `mistral-medium` (or `mistral-small`)

---

### 7. **config.py** - Configuration Management
**Kaam:**
- API tokens ko automatically load karta hai
- Environment variables setup karta hai

**Key Functions:**

#### `load_token_from_file()`
- `token.md` ya `.env` file se token read karta hai
- Multiple formats support karta hai:
  - PowerShell: `$env:HF_TOKEN = "token"`
  - Standard: `HF_TOKEN=token`
  - Mistral: `MISTRAL_API_KEY=token`

#### `setup_environment()`
- Environment variables set karta hai
- Token format detect karta hai (HF vs Mistral)

---

### 8. **templates/index.html** - Web UI
**Kaam:**
- User-friendly web interface provide karta hai
- Form for URL input aur field selection

**Features:**
- Predefined fields checkbox selection
- Custom fields input
- Real-time loading indicator
- Formatted results display

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    USER REQUEST                          │
│  (Web Form ya CLI se URL + Fields)                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   app.py (Flask)                         │
│  - /api/extract endpoint receive karta hai               │
│  - setup_environment() call karta hai                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              pipeline.py → run(url, fields)              │
│                                                          │
│  Step 1: Screenshot Capture                             │
│  ┌──────────────────────────────────────┐              │
│  │ capture_fullpage(url)                │              │
│  │ → capture.py → Playwright            │              │
│  │ → tmp_page.png save hota hai          │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 2: Text Extraction (2 methods try)                │
│  ┌──────────────────────────────────────┐              │
│  │ Method 1: DOM Extraction             │              │
│  │ → scrape_dom.py                      │              │
│  │   - fetch_dom_text() (BeautifulSoup) │              │
│  │   - fetch_dom_with_playwright()      │              │
│  └──────────────────────────────────────┘              │
│  ┌──────────────────────────────────────┐              │
│  │ Method 2: OCR (Fallback)             │              │
│  │ → ocr.py                              │              │
│  │   - ocr_easyocr()                    │              │
│  │   - ocr_pytesseract()                │              │
│  │   - Combine both results             │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 3: Prompt Generation                               │
│  ┌──────────────────────────────────────┐              │
│  │ generate_prompt_template(fields)      │              │
│  │ - Field definitions add karta hai     │              │
│  │ - Extraction rules add karta hai      │              │
│  │ - Custom fields handle karta hai       │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 4: AI Model Call                                   │
│  ┌──────────────────────────────────────┐              │
│  │ call_hf_inference(prompt)             │              │
│  │ → call_model_hf.py                    │              │
│  │   - HuggingFace API ya Mistral API    │              │
│  │   - Token authentication              │              │
│  │   - Retry logic                       │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 5: JSON Parsing                                    │
│  ┌──────────────────────────────────────┐              │
│  │ - Extract JSON from model response    │              │
│  │ - Validate field types                │              │
│  │ - Apply fallback values (regex)       │              │
│  │ - Filter to requested fields only     │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│              RETURN JSON RESULT                          │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              app.py → JSON Response                     │
│              → Web UI ya CLI output                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Features

### 1. **Dual Extraction Strategy**
- **DOM First:** Fast, accurate, structured data
- **OCR Fallback:** Works for any site, visual content handle karta hai

### 2. **Field Flexibility**
- **Predefined Fields:** rating, price, mrp, etc. (with detailed rules)
- **Custom Fields:** Any field name (e.g., "Operating System", "SELECT SIZE")

### 3. **AI-Powered Extraction**
- Mistral 7B Instruct model use karta hai
- Line-by-line reading instructions
- OCR errors handle karta hai
- Structured JSON output

### 4. **Error Handling**
- Multiple fallback strategies
- Retry logic with exponential backoff
- Graceful degradation

### 5. **Site-Specific Handling**
- Amazon: Longer timeouts
- Flipkart: Networkidle wait
- Myntra: Multiple anti-bot strategies
- Generic: Default strategy

---

## 📝 Usage Examples

### CLI Usage:
```bash
# Basic usage
python pipeline.py "https://www.flipkart.com/product-url"

# With specific fields
python pipeline.py "https://..." rating price mrp

# PowerShell script
.\run_pipeline.ps1 -Url "https://..." -Fields rating,price
```

### Web UI:
```bash
python app.py
# Open http://localhost:5000
```

### API Usage:
```bash
curl -X POST http://localhost:5000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://...", "fields": ["rating", "price"]}'
```

---

## 🛠️ Dependencies

**Main Libraries:**
- `playwright` - Browser automation
- `flask` - Web server
- `easyocr` / `pytesseract` - OCR
- `beautifulsoup4` - HTML parsing
- `requests` - API calls

**Model APIs:**
- HuggingFace Inference API
- Mistral API

---

## ⚙️ Configuration

**Token Setup:**
1. `token.md` file me:
   ```
   $env:HF_TOKEN = "hf_..."
   ```
   ya
   ```
   $env:MISTRAL_API_KEY = "your_key"
   ```

2. Ya `.env` file me:
   ```
   HF_TOKEN=hf_...
   ```

**Environment Variables:**
- `HF_TOKEN` - HuggingFace token
- `MISTRAL_API_KEY` - Mistral API key
- `PORT` - Flask server port (default: 5000)

---

## 🎯 Summary

**Yeh system:**
1. Product URL le ke screenshot capture karta hai
2. Text extract karta hai (DOM ya OCR se)
3. AI model ko prompt bhejta hai with extraction rules
4. Structured JSON me data return karta hai

**Key Advantage:**
- Works with any e-commerce site
- Custom fields support
- Visual content (screenshots) se bhi extract karta hai
- AI-powered, accurate extraction

---

## 📊 File Dependencies

```
app.py
  ├── pipeline.py (run function)
  │     ├── capture.py (screenshot)
  │     ├── ocr.py (text from image)
  │     ├── scrape_dom.py (text from HTML)
  │     └── call_model_hf.py (AI model)
  └── config.py (token loading)
```

---

**End of Explanation** 🎉

