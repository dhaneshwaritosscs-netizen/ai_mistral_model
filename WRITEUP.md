# Meesho Product Review Extraction — Writeup

## Project overview

This repository implements an end-to-end pipeline to extract customer review information (rating, ratings count, reviews count, and review text) from product pages (e.g., Meesho, Amazon-like pages). It combines DOM scraping, full-page screenshots, OCR (EasyOCR and pytesseract), and an LLM (Hugging Face or Mistral) to produce a structured JSON output.

Key goals:
- Reliably extract rating and review text from pages where DOM extraction may not be available or reliable.
- Use OCR as a fallback for images or when reviews are rendered client-side.
- Use an LLM to robustly parse noisy OCR output into structured JSON.

## Files and responsibilities

- `pipeline.py` — Orchestrator: tries DOM extraction first, falls back to OCR, calls the model to extract structured data, performs regex fallbacks.
- `capture.py` — Playwright-based page capture helper (`capture_fullpage`) to save screenshots (uses `playwright` and `Pillow`).
- `ocr.py` — OCR helpers: `ocr_easyocr` (EasyOCR) and `ocr_pytesseract` wrappers for extracting text from screenshots.
- `call_model_hf.py` — Model integration: calls either Hugging Face inference API or Mistral API and extracts generated text. Includes retry logic.
- `scrape_dom.py` — (Referenced in README and pipeline) DOM-based extraction helpers (fetching text via requests or Playwright). Not all functions may be shown in this snapshot—check file for available helpers.
- `requirements.txt` — Lists main Python dependencies (playwright, pillow, pytesseract, requests, beautifulsoup4, easyocr).
- `run_pipeline.ps1`, `run_pipeline.bat` — Helper scripts to run the end-to-end pipeline with a URL on Windows.

## How the pipeline works (high level)

1. Attempt DOM extraction (fast, higher precision): `fetch_dom_text` or `fetch_dom_with_playwright` from `scrape_dom.py`.
2. If DOM text is insufficient or unavailable, capture a screenshot using `capture_fullpage` (Playwright) and extract text using EasyOCR and/or pytesseract.
3. Create a structured prompt (see `REVIEW_PROMPT_TEMPLATE` in `pipeline.py`) and call the LLM via `call_hf_inference` (Hugging Face / Mistral) to parse the noisy text into JSON.
4. If the model output is missing or unparseable, pipeline uses robust regex-based fallbacks to extract rating, ratings_count and reviews_count.

## Inputs and outputs (contract)

- Input: a product page URL (string).
- Output: a JSON/dict with keys:
  - `rating`: float or null (0–5)
  - `ratings_count`: int or null
  - `reviews_count`: int or null
  - `review`: string or null
  - `source`: one of `dom` or `ocr` indicating origin of text
  - Optionally `error` or `note` fields for debugging

Error modes:
- Network/Playwright errors while capturing.
- Tesseract not installed or missing binary.
- Missing or rate-limited Hugging Face / Mistral API token.
- Model output not parsable as JSON (handled via fallbacks).

Success criteria:
- Returns a dict with at least the `source` and any available fields filled.
- If no useful data could be extracted, returns nulls with an explanatory `error`.

## Setup (Windows / PowerShell)

Prerequisites:
- Python 3.9+
- Tesseract OCR installed and in PATH (Windows: UB Mannheim build recommended)
- `HF_TOKEN` or `MISTRAL_API_KEY` set for model calls

Install dependencies and Playwright browsers (PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install
```

Set Hugging Face token (PowerShell):

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

If Tesseract binary isn't in PATH, set `pytesseract.pytesseract.tesseract_cmd` in `ocr.py` (commented guidance already present).

## Quick run (examples)

PowerShell (recommended helper script):

```powershell
# Use the provided wrapper
.\run_pipeline.ps1 "https://www.meesho.com/your-product-url"
```

Manual run:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
python pipeline.py "https://www.meesho.com/your-product-url"
```

Individual component runs (for debugging):
- Capture screenshot (edit URL in `capture.py`): `python capture.py` (produces `product_page.png` or similar)
- OCR test: ensure image exists, then `python ocr.py`
- Model call test: `python call_model_hf.py`

## Troubleshooting (common issues & fixes)

- TesseractNotFound: Install Tesseract and add to PATH. On Windows, update `pytesseract.pytesseract.tesseract_cmd` if needed.
- Playwright browser errors: run `python -m playwright install chromium` (or `playwright install` variants).
- HF API errors: ensure `HF_TOKEN` is set and valid; be aware of rate-limits and model access.
- OCR poor quality: crop to relevant review area, increase viewport height/width, preprocess image (contrast/denoise), or use EasyOCR (likely better for mixed fonts).
- Model output parsing: the code tries to extract JSON from code blocks and loose responses; if the model frequently returns non-JSON, try lowering temperature to 0.0 or adjusting the prompt to force only JSON.

## Design notes and rationale

- DOM-first: DOM scraping is used first because it is more accurate and avoids OCR noise.
- OCR fallback: essential for pages where reviews are rendered as images or heavily client-side.
- LLM parser: using an LLM to convert noisy text into structured JSON is more robust than pure regex rules. However, always keep regex fallbacks for edge cases and reduced latency.
- Dual model support: `call_model_hf.py` supports both Hugging Face inference and direct Mistral API usage depending on token format.

## Edge cases and considerations

- Pages with multiple reviews: pipeline extracts the most prominent review by prompt guidance. If multiple reviews are required, adjust the prompt and parsing logic.
- Locale-specific number formats (e.g., Indian grouping `3,34,015`): regex handles some variants but may need further tuning.
- Pages behind strict bot detection: Playwright can be tuned with headers and waits; you may need to use proxies or longer waits.
- Performance: full-page screenshots and OCR are the heaviest steps—consider cropping to the review area when possible.

## Testing suggestions

Recommended minimal tests (unittests or pytest):
- Unit test for `ocr.py` functions using a small sample image fixture.
- Unit test for regex fallback functions with representative noisy strings (Indian format, split decimals, star symbols).
- Integration test: a short run of `pipeline.run(url)` mocked with a canned DOM or OCR output to assert JSON output shape.

## Next steps and improvements

Short-term (low risk):
- Add `--crop` option to `capture_fullpage` to only capture review area (speeds OCR and improves accuracy).
- Add unit tests for regex extraction and JSON parsing.
- Add configurable model selection (via env var) and explicit temperature=0 for deterministic outputs.

Medium-term:
- Add async versions for throughput and queue worker processing.
- Add retries and backoff for Playwright navigation with more robust headless browser anti-bot handling.
- Add a small web UI or CLI that processes a list of URLs and outputs a CSV/JSONL.

Long-term:
- Train or fine-tune a smaller, task-specific model for structured extraction from OCR text to reduce reliance on external LLM calls and latency.
- Add rate-limit-aware batching for HF/Mistral calls and implement caching of previously processed pages.

## Where I saved this writeup

- `WRITEUP.md` in repository root (this file).

## Quality gates (notes)

- Build: Not executed in this session—dependencies are listed in `requirements.txt`.
- Lint/typecheck: Not executed here; consider adding `flake8`/`ruff`/`mypy` and CI in future.
- Tests: No tests present; recommended tests outlined above.

---

If you want, I can:
- Save this writeup into the repo (already done: `WRITEUP.md`).
- Add unit tests for the regex extraction and a minimal integration test for `pipeline.run` (mock the network/OCR/model).
- Create a short README section with troubleshooting checklists (expand current README).

Tell me which follow-up you'd like (tests, CI, cropping feature, or anything else) and I'll implement it next. 