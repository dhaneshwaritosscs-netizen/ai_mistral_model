# 📋 Project Handover Document
## AI-Powered Product Data Extraction System

**Project Name:** AI Meesho Mistral - Product Data Extraction System  
**Technology Stack:** Python, Flask, Playwright, OCR (EasyOCR/Tesseract), Mistral AI  
**Purpose:** E-commerce product pages से structured data extract करने के लिए AI-powered system

---

## 🎯 Project Overview (प्रोजेक्ट अवलोकन)

यह एक **end-to-end AI-powered product data extraction system** है जो:
- Product page URLs से automatically data extract करता है
- Multiple extraction methods use करता है (DOM scraping, OCR, AI)
- Structured JSON format में data return करता है
- Web interface और API दोनों provide करता है

### Key Features:
1. **Dual Extraction Strategy:** DOM scraping (fast) + OCR fallback (universal)
2. **AI-Powered Parsing:** Mistral 7B model use करके noisy OCR text को structured JSON में convert करता है
3. **Flexible Field Extraction:** Predefined fields (rating, price, MRP) + custom fields support
4. **Multi-Site Support:** Amazon, Flipkart, Myntra, Meesho जैसे sites के लिए optimized
5. **Anti-Bot Detection Bypass:** Playwright के साथ advanced techniques use करता है

---

## 🏗️ System Architecture (सिस्टम आर्किटेक्चर)

### High-Level Flow:

```
┌─────────────────────────────────────────────────────────┐
│                    USER REQUEST                          │
│  (Web UI / CLI / API - URL + Fields)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Flask Web Server                       │
│                   (app.py)                               │
│  - /api/extract endpoint                                 │
│  - /api/fields endpoint                                  │
│  - /api/upload-csv endpoint                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Main Pipeline (pipeline.py)                 │
│                                                          │
│  Step 1: Screenshot Capture                             │
│  ┌──────────────────────────────────────┐              │
│  │ capture_fullpage(url)                 │              │
│  │ → capture.py → Playwright             │              │
│  │ → tmp_page.png save                   │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 2: Text Extraction (2 methods)                    │
│  ┌──────────────────────────────────────┐              │
│  │ Method 1: DOM Extraction             │              │
│  │ → scrape_dom.py                      │              │
│  │   - fetch_dom_text() (BeautifulSoup) │              │
│  │   - fetch_dom_with_playwright()      │              │
│  └──────────────────────────────────────┘              │
│  ┌──────────────────────────────────────┐              │
│  │ Method 2: OCR (Fallback)            │              │
│  │ → ocr.py                              │              │
│  │   - ocr_easyocr()                    │              │
│  │   - ocr_pytesseract()                │              │
│  │   - Combine both results             │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 3: AI Model Processing                            │
│  ┌──────────────────────────────────────┐              │
│  │ generate_prompt_template(fields)      │              │
│  │ → call_hf_inference(prompt)          │              │
│  │ → call_model_hf.py                    │              │
│  │   - HuggingFace API / Mistral API    │              │
│  │   - Local model (if available)       │              │
│  └──────────────────────────────────────┘              │
│                     │                                    │
│                     ▼                                    │
│  Step 4: JSON Parsing & Validation                      │
│  ┌──────────────────────────────────────┐              │
│  │ - Extract JSON from model response   │              │
│  │ - Validate field types                │              │
│  │ - Apply regex fallbacks               │              │
│  │ - Return structured JSON              │              │
│  └──────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              JSON Response to User                      │
│              {                                          │
│                "rating": 4.3,                          │
│                "price": "₹592",                        │
│                "mrp": "₹1,302",                       │
│                "source": "ocr"                         │
│              }                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 File Structure & Responsibilities (फाइल संरचना)

### Core Files:

#### 1. **app.py** - Flask Web Server
**Purpose:** Main web application entry point

**Key Functions:**
- `@app.route('/')` - Homepage render करता है
- `@app.route('/api/extract', methods=['POST'])` - Single/Multiple URLs से data extract करता है
- `@app.route('/api/extract/batch', methods=['POST'])` - Batch processing के लिए
- `@app.route('/api/upload-csv', methods=['POST'])` - CSV file से URLs process करता है
- `@app.route('/api/fields', methods=['GET'])` - Available fields list return करता है

**Usage:**
```bash
python app.py
# Server starts on http://localhost:5010
```

---

#### 2. **pipeline.py** - Main Processing Logic ⭐ (सबसे Important)
**Purpose:** Complete extraction pipeline को orchestrate करता है

**Key Functions:**

**`run(url, fields=None, use_dom_first=True, use_ocr_fallback=True)`**
- Main function जो complete flow handle करता है
- Parameters:
  - `url`: Product page URL
  - `fields`: List of fields to extract (e.g., ['rating', 'price', 'mrp'])
  - `use_dom_first`: DOM extraction try करना है या नहीं
  - `use_ocr_fallback`: OCR fallback use करना है या नहीं
- Returns: Dictionary with extracted fields + source

**`generate_prompt_template(fields)`**
- Requested fields के लिए dynamic prompt generate करता है
- Predefined fields (rating, price, etc.) और custom fields दोनों support करता है
- Detailed extraction rules add करता है

**Predefined Fields:**
- `rating` - Product rating (0.0 to 5.0)
- `ratings_count` - Total ratings count
- `reviews_count` - Total reviews count
- `review` - Customer review text
- `price` - Current price (non-crossed-out)
- `mrp` - Maximum Retail Price (crossed-out price)
- `product_name` - Product title
- `discount` / `markdown` - Discount percentage
- `availability` - Stock status
- `synonyms` - Product synonyms/alternative names

**Custom Fields Support:**
- कोई भी custom field name pass कर सकते हैं (e.g., "Operating System", "SELECT SIZE")
- System automatically extraction rules generate करता है

**Flow:**
1. Screenshot capture (always)
2. DOM extraction try करता है (fast, accurate)
3. OCR fallback (if DOM fails or insufficient)
4. AI model call with dynamic prompt
5. JSON parsing और validation
6. Regex fallbacks (if model fails)

---

#### 3. **capture.py** - Screenshot Capture
**Purpose:** Playwright use करके web pages का screenshot लेता है

**Key Functions:**

**`capture_fullpage(url, out_path="tmp_page.png")`**
- Main function जो screenshot capture करता है
- Site-specific handling:
  - Amazon: Longer timeouts
  - Flipkart: Networkidle wait
  - Myntra: Multiple anti-bot strategies
  - Generic: Default strategy

**Anti-Bot Detection Techniques:**
- User agent spoofing
- Webdriver property removal
- Realistic browser context
- Extra headers
- Popup closing (comprehensive)

**`_capture_myntra(url, out_path)`**
- Myntra के लिए special handling (strong bot detection)
- Multiple strategies try करता है:
  1. Mobile user agent
  2. Chromium stealth mode
  3. Non-headless browser
  4. Firefox browser
  5. Alternative Chromium settings

---

#### 4. **ocr.py** - Text Extraction from Images
**Purpose:** Screenshot images से text extract करता है

**Key Functions:**

**`ocr_easyocr(image_path, lang_list=['en'])`**
- EasyOCR use करता है (better for mixed fonts)
- Line-by-line structure preserve करता है
- Bounding boxes से text ordering maintain करता है

**`ocr_pytesseract(image_path)`**
- Tesseract OCR use करता है
- Simpler but faster
- Line structure preserve करता है

**Why Both?**
- EasyOCR: Better accuracy, mixed fonts handle करता है
- Tesseract: Faster, simpler text
- Combine करके maximum text extraction

---

#### 5. **scrape_dom.py** - DOM Text Extraction
**Purpose:** HTML DOM से directly text extract करता है

**Key Functions:**

**`fetch_dom_text(url)`**
- BeautifulSoup use करके simple HTML parse करता है
- Fast but JavaScript content miss हो सकता है

**`fetch_dom_with_playwright(url)`**
- Playwright use करके JS-rendered content handle करता है
- Networkidle wait करता है (dynamic content load होने के लिए)

**`extract_rating_from_dom(url)`**
- DOM attributes से rating directly extract करता है
- Flipkart/Amazon के लिए specific selectors use करता है

---

#### 6. **call_model_hf.py** - AI Model Integration
**Purpose:** HuggingFace Inference API, Mistral API, और local model को call करता है

**Key Functions:**

**`call_hf_inference(prompt, use_mistral_api=False)`**
- HuggingFace API call करता है
- Retry logic with exponential backoff
- Token authentication handle करता है

**`call_mistral_api(prompt)`**
- Mistral API directly call करता है
- Rate limit handling
- Timeout handling for large prompts

**`call_local_model(prompt)`**
- Local Mistral model use करता है (if available)
- No API needed
- Requires model files in directory

**`extract_json_from_response(resp, is_mistral=False, is_local=False)`**
- API response से generated text extract करता है
- Different response formats handle करता है

**Model Priority:**
1. Local model (if available) - No API cost
2. Mistral API (if MISTRAL_API_KEY set)
3. HuggingFace API (if HF_TOKEN set)

---

#### 7. **config.py** - Configuration Management
**Purpose:** API tokens को automatically load करता है

**Key Functions:**

**`load_token_from_file()`**
- `token.md` या `.env` file से token read करता है
- Multiple formats support करता है:
  - PowerShell: `$env:HF_TOKEN = "token"`
  - Standard: `HF_TOKEN=token`
  - Mistral: `MISTRAL_API_KEY=token`

**`setup_environment()`**
- Environment variables set करता है
- Token format detect करता है (HF vs Mistral)

**Token Setup:**
1. Create `token.md` file:
   ```
   $env:HF_TOKEN = "hf_your_token_here"
   ```
   या
   ```
   $env:MISTRAL_API_KEY = "your_mistral_key"
   ```

2. या create `.env` file:
   ```
   HF_TOKEN=hf_your_token_here
   ```

---

#### 8. **templates/index.html** - Web UI
**Purpose:** User-friendly web interface provide करता है

**Features:**
- Predefined fields checkbox selection
- Custom fields input
- Real-time loading indicator
- Formatted results display
- CSV upload support
- Multiple URLs support

---

### Supporting Files:

- **requirements.txt** - Python dependencies
- **run_pipeline.bat** / **run_pipeline.ps1** - CLI wrapper scripts
- **run_web.bat** / **run_web.ps1** - Web server startup scripts
- **link.csv** - Sample CSV file for batch processing
- **token.md** - API token storage (gitignore में add करें)

---

## 🚀 Setup Instructions (सेटअप निर्देश)

### Prerequisites:
1. **Python 3.9+** installed
2. **Tesseract OCR** installed और PATH में
   - Windows: [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) download करें
3. **API Token** (HuggingFace या Mistral)

### Step-by-Step Setup:

#### 1. Clone/Download Project
```bash
cd D:\model_train\ai_meesho_mistral (2)\ai_meesho_mistral
```

#### 2. Create Virtual Environment
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

#### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 4. Install Playwright Browsers
```powershell
python -m playwright install chromium
```

#### 5. Setup API Token
Create `token.md` file:
```
$env:HF_TOKEN = "hf_your_token_here"
```
या
```
$env:MISTRAL_API_KEY = "your_mistral_key"
```

#### 6. Verify Tesseract Installation
```powershell
tesseract --version
```
If not found, add Tesseract to PATH या `ocr.py` में path set करें:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

---

## 💻 Usage Examples (उपयोग उदाहरण)

### 1. Web UI (Recommended)
```powershell
python app.py
# Open http://localhost:5010 in browser
```

**Features:**
- Single URL extraction
- Multiple URLs (comma-separated)
- CSV file upload
- Field selection (predefined + custom)
- Real-time results

### 2. CLI Usage
```powershell
# Basic usage
python pipeline.py "https://www.flipkart.com/product-url"

# With specific fields
python pipeline.py "https://..." rating price mrp

# Using PowerShell script
.\run_pipeline.ps1 -Url "https://..." -Fields rating,price,mrp
```

### 3. API Usage
```bash
# Single URL
curl -X POST http://localhost:5010/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://...", "fields": ["rating", "price"]}'

# Multiple URLs
curl -X POST http://localhost:5010/api/extract \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://...", "https://..."], "fields": ["rating", "price"]}'
```

### 4. Batch Processing (CSV)
```bash
# Upload CSV file via web UI
# CSV format: First column should contain URLs
```

---

## 🔧 Configuration (कॉन्फ़िगरेशन)

### Environment Variables:
- `HF_TOKEN` - HuggingFace API token
- `MISTRAL_API_KEY` - Mistral API key
- `PORT` - Flask server port (default: 5010)

### Model Configuration:
- **Default Model:** `mistralai/Mistral-7B-Instruct-v0.2`
- **Local Model:** If model files exist in directory, local model use होगा
- **Model Priority:** Local > Mistral API > HuggingFace API

### Field Configuration:
Predefined fields `pipeline.py` में `FIELD_DEFINITIONS` dictionary में define हैं। Custom fields automatically handle होते हैं।

---

## 🐛 Troubleshooting (समस्या निवारण)

### Common Issues:

#### 1. TesseractNotFound Error
**Problem:** Tesseract OCR not found
**Solution:**
- Install Tesseract और PATH में add करें
- या `ocr.py` में path manually set करें:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  ```

#### 2. Playwright Browser Errors
**Problem:** Browser not installed
**Solution:**
```powershell
python -m playwright install chromium
```

#### 3. API Token Errors
**Problem:** `HF_TOKEN` or `MISTRAL_API_KEY` not set
**Solution:**
- Create `token.md` file with token
- या environment variable set करें:
  ```powershell
  $env:HF_TOKEN = "your_token"
  ```

#### 4. OCR Poor Quality
**Problem:** OCR text extraction poor quality
**Solution:**
- Screenshot quality check करें
- EasyOCR use करें (better accuracy)
- Image preprocessing add करें (contrast/denoise)

#### 5. Model Output Parsing Failed
**Problem:** Model returns non-JSON output
**Solution:**
- System automatically regex fallbacks use करता है
- Prompt adjust करें (if needed)
- Temperature 0.0 use करें (deterministic output)

#### 6. Bot Detection (Myntra/Flipkart)
**Problem:** Site blocks requests
**Solution:**
- System automatically multiple strategies try करता है
- Wait time increase करें
- Proxy use करें (if needed)

---

## 📊 Technical Details (तकनीकी विवरण)

### Extraction Strategy:

1. **DOM First (Fast & Accurate)**
   - BeautifulSoup: Simple HTML parsing
   - Playwright: JavaScript-rendered content
   - Direct attribute extraction (for ratings)

2. **OCR Fallback (Universal)**
   - EasyOCR: Better accuracy, mixed fonts
   - Tesseract: Faster, simpler text
   - Combined results for maximum coverage

3. **AI Processing**
   - Dynamic prompt generation based on requested fields
   - Line-by-line reading instructions
   - OCR error handling
   - Structured JSON output

4. **Validation & Fallbacks**
   - Type validation (decimal, integer, string)
   - Regex fallbacks for critical fields
   - Cross-validation (price vs MRP)
   - Error handling at each step

### Performance Considerations:

- **Screenshot Capture:** ~2-5 seconds (depends on site)
- **DOM Extraction:** ~1-2 seconds (fast)
- **OCR Processing:** ~5-15 seconds (depends on image size)
- **AI Model Call:** ~3-10 seconds (depends on API/model)
- **Total Time:** ~10-30 seconds per URL

### Scalability:

- **Single URL:** Sequential processing
- **Multiple URLs:** Sequential (can be parallelized)
- **Batch Processing:** CSV upload support
- **API Rate Limits:** Retry logic with exponential backoff

---

## 🔐 Security Considerations (सुरक्षा विचार)

1. **Token Storage:**
   - `token.md` file को `.gitignore` में add करें
   - Environment variables use करें (production में)

2. **API Keys:**
   - Never commit tokens to git
   - Use secure storage methods

3. **Input Validation:**
   - URL validation (basic)
   - Field name sanitization

---

## 📈 Future Improvements (भविष्य के सुधार)

### Short-term:
- [ ] Add `--crop` option for screenshot (faster OCR)
- [ ] Unit tests for regex extraction
- [ ] Configurable model selection
- [ ] Better error messages

### Medium-term:
- [ ] Async processing for multiple URLs
- [ ] Queue worker for batch processing
- [ ] Caching of processed pages
- [ ] Rate-limit aware batching

### Long-term:
- [ ] Fine-tune smaller task-specific model
- [ ] Multi-language support
- [ ] Advanced image preprocessing
- [ ] Real-time monitoring dashboard

---

## 📝 Important Notes (महत्वपूर्ण नोट्स)

1. **Screenshot Always Captured:** System हमेशा screenshot capture करता है (user requirement)

2. **Full Text Extraction:** OCR से extracted text को कभी truncate नहीं करता - complete text use करता है

3. **Custom Fields:** कोई भी custom field name pass कर सकते हैं - system automatically rules generate करता है

4. **Field Extraction:** जब field name मिलता है, तो उसके नीचे की सभी content extract करता है जब तक next section/title नहीं मिलता

5. **Price/MRP Validation:**
   - Price: Non-crossed-out (current price)
   - MRP: Crossed-out price (near current price, NOT from ratings section)
   - System automatically validates और warnings देता है

6. **Model Priority:**
   - Local model (if available) - No cost
   - Mistral API - Better quality
   - HuggingFace API - Fallback

---

## 📞 Support & Contact (सहायता)

### Documentation Files:
- `PROJECT_FLOW_EXPLANATION.md` - Detailed flow explanation (Hindi/English)
- `WRITEUP.md` - Technical writeup
- `README.md` - Model card information
- `HANDOVER_DOCUMENT.md` - This file

### Key Files to Understand:
1. **pipeline.py** - Main logic (most important)
2. **app.py** - Web server
3. **capture.py** - Screenshot capture
4. **call_model_hf.py** - AI model integration
5. **config.py** - Configuration

---

## ✅ Handover Checklist (हैंडओवर चेकलिस्ट)

- [x] Project structure documented
- [x] Setup instructions provided
- [x] Usage examples included
- [x] Troubleshooting guide added
- [x] Technical details explained
- [x] File responsibilities documented
- [x] Configuration guide included
- [x] Security considerations noted

---

## 🎯 Quick Start Guide (त्वरित प्रारंभ गाइड)

### For New Developer:

1. **Setup Environment:**
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

2. **Configure Token:**
   - Create `token.md` with your API token

3. **Test Run:**
   ```powershell
   python app.py
   # Open http://localhost:5010
   ```

4. **Understand Flow:**
   - Read `pipeline.py` - Main logic
   - Read `PROJECT_FLOW_EXPLANATION.md` - Detailed flow

5. **Start Development:**
   - Modify `pipeline.py` for new features
   - Add new fields in `FIELD_DEFINITIONS`
   - Test with real URLs

---

## 📚 Additional Resources (अतिरिक्त संसाधन)

- **Playwright Documentation:** https://playwright.dev/python/
- **EasyOCR Documentation:** https://github.com/JaidedAI/EasyOCR
- **Tesseract OCR:** https://github.com/tesseract-ocr/tesseract
- **Mistral AI:** https://docs.mistral.ai/
- **HuggingFace:** https://huggingface.co/docs/api-inference

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Maintained By:** Development Team

---

## 🎉 Summary (सारांश)

यह system एक **powerful AI-powered product data extraction tool** है जो:
- Multiple extraction methods combine करता है
- AI use करके accurate results देता है
- Flexible field extraction support करता है
- Web UI और API दोनों provide करता है
- Production-ready है with proper error handling

**Key Advantage:** Works with any e-commerce site, handles visual content, और AI-powered accurate extraction provide करता है।

---

**End of Handover Document** 🎉

