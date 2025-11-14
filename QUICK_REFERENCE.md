# ⚡ Quick Reference Guide
## AI Product Data Extraction System

---

## 🚀 Quick Start (5 Minutes)

### 1. Setup
```powershell
# Activate virtual environment
venv\Scripts\Activate.ps1

# Install dependencies (if not done)
pip install -r requirements.txt
python -m playwright install chromium

# Setup token
# Create token.md file:
$env:HF_TOKEN = "hf_your_token_here"
```

### 2. Run Web UI
```powershell
python app.py
# Open http://localhost:5010
```

### 3. Run CLI
```powershell
python pipeline.py "https://www.flipkart.com/product-url" rating price mrp
```

---

## 📁 Key Files

| File | Purpose | When to Modify |
|-----|---------|----------------|
| `pipeline.py` | Main extraction logic | Add new fields, change extraction logic |
| `app.py` | Flask web server | Add new API endpoints |
| `capture.py` | Screenshot capture | Change browser settings, anti-bot strategies |
| `ocr.py` | Text extraction from images | Change OCR settings |
| `call_model_hf.py` | AI model integration | Change model, API settings |
| `config.py` | Token configuration | Change token loading logic |

---

## 🔧 Common Tasks

### Add New Field
1. Open `pipeline.py`
2. Add to `FIELD_DEFINITIONS` dictionary:
```python
"new_field": {
    "description": "Field description",
    "rules": ["Rule 1", "Rule 2"],
    "type": "string",  # or "integer", "decimal"
    "example": "example value"
}
```

### Change Model
Edit `call_model_hf.py`:
```python
MODEL = "mistralai/Mistral-7B-Instruct-v0.2"  # Change here
```

### Add Custom Field (No Code Change)
Just pass field name in API/CLI:
```python
fields = ["Operating System", "SELECT SIZE", "Brand"]
```

### Change Screenshot Settings
Edit `capture.py` → `capture_fullpage()` function

---

## 🐛 Quick Fixes

### Token Not Working
```powershell
# Check token.md exists
# Or set environment variable:
$env:HF_TOKEN = "your_token"
```

### Tesseract Error
```python
# In ocr.py, add:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Playwright Error
```powershell
python -m playwright install chromium
```

### Port Already in Use
```powershell
# Change port in app.py or set:
$env:PORT = "5011"
```

---

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Web UI |
| `/api/extract` | POST | Extract from single/multiple URLs |
| `/api/extract/batch` | POST | Batch processing |
| `/api/upload-csv` | POST | Process CSV file |
| `/api/fields` | GET | Get available fields |

---

## 🎯 Predefined Fields

- `rating` - Product rating (0.0-5.0)
- `ratings_count` - Total ratings
- `reviews_count` - Total reviews
- `review` - Review text
- `price` - Current price
- `mrp` - Maximum Retail Price
- `product_name` - Product title
- `discount` / `markdown` - Discount %
- `availability` - Stock status
- `synonyms` - Product synonyms

---

## 💡 Tips

1. **Always capture screenshot** - System does this automatically
2. **Use full text** - Never truncate OCR text
3. **Custom fields work** - Just pass field name, no code needed
4. **Model priority:** Local > Mistral API > HuggingFace API
5. **DOM first, OCR fallback** - Fast and accurate

---

## 📞 Need Help?

1. Check `HANDOVER_DOCUMENT.md` for detailed info
2. Check `PROJECT_FLOW_EXPLANATION.md` for flow details
3. Check error messages - they're descriptive
4. Check console output - shows each step

---

**Quick Reference Version:** 1.0

