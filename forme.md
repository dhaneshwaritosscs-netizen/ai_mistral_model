Server
app.py runs the Flask server. It receives requests from the web UI or API and calls pipeline.run(url, fields).

Screenshot
capture.py uses Playwright (Chromium) to open the URL in headless mode, close popups, and take a full-page screenshot → tmp_page.png.

Text Extraction
The DOM is tried first: scrape_dom.py extracts text using Requests + BeautifulSoup or a Playwright-rendered DOM.
If the DOM is blocked or insufficient, it falls back to OCR: ocr.py uses EasyOCR + Tesseract to extract text from tmp_page.png.

Prompt + Model
In pipeline.py, a prompt is created based on the requested attributes (with strict rules for things like price vs MRP, rating, etc.).
call_model_hf.py then calls the model (Mistral API or Hugging Face API; if no token is available, it uses local weights).

Parse + Output
The model’s text output is parsed into JSON, validated, and only the requested fields are returned.

Final Response
Finally, app.py returns the result as a JSON response (return jsonify).