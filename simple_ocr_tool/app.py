import sys
import os
import uuid
import requests
import re
import csv
import threading
import time
import io
from flask import Flask, render_template, request, jsonify, send_file
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add parent directory to path to find ocr.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ocr import ocr_easyocr, ocr_pytesseract

app = Flask(__name__)

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Task Management
tasks = {} # task_id -> { progress, total, results, status, stop_event }

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
    """Download image from URL to a temporary file with retry logic"""
    try:
        url = convert_google_drive_link(url)
        
        # User-Agent headers to look like a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://www.google.com/"
        }

        # Setup retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        response = session.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        
        ext = 'jpg'
        if 'content-type' in response.headers:
            ct = response.headers['content-type']
            if 'image/' in ct:
                ext = ct.split('/')[-1]
        
        temp_filename = os.path.join(app.config['UPLOAD_FOLDER'], f"tmp_web_{uuid.uuid4().hex}.{ext}")
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_filename
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error downloading {url}: {e}")
        # Identify NameResolutionError specifically
        if "getaddrinfo failed" in str(e):
            print(f"DNS Resolution failed for {url}. Please check your internet connection or DNS settings.")
        return None
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

def filter_garbage_text(text):
    """Filter out garbage text, symbols, and non-English characters."""
    if not text:
        return "No text found"
    cleaned_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        cleaned_line = re.sub(r'[^A-Za-z0-9\s.,!?;:()\'"₹$€£%-]', '', line).strip()
        if not cleaned_line: continue
        words = [w for w in cleaned_line.split() if w]
        is_price = any(c in cleaned_line for c in '₹$€£') or bool(re.search(r'\d+[.,]\d+', cleaned_line))
        alpha_words = ["".join(filter(str.isalpha, w)) for w in words]
        long_words = [w for w in alpha_words if len(w) >= 4]
        mid_words = [w for w in alpha_words if len(w) >= 3]
        if is_price or (len(long_words) >= 1 or len(mid_words) >= 2):
            if len(cleaned_line) > 2:
                cleaned_lines.append(cleaned_line)
    result = "\n".join(cleaned_lines).strip()
    return result if result else "No text found"

def extract_text_from_file(image_path):
    """Extract text from image using optimized dual-OCR logic."""
    try:
        easyocr_text = ocr_easyocr(image_path, lang_list=['en', 'hi'])
        if len(easyocr_text.strip()) > 50:
            return filter_garbage_text(easyocr_text), "EasyOCR"
        else:
            try: tesseract_text = ocr_pytesseract(image_path)
            except: tesseract_text = ""
            if len(tesseract_text) > len(easyocr_text):
                return filter_garbage_text(tesseract_text), "Tesseract"
            else:
                return filter_garbage_text(easyocr_text), "EasyOCR (fallback)"
    except Exception as e:
        return f"Error: {str(e)}", "Error"

def process_bulk_csv(task_id, rows):
    """Background worker for CSV processing."""
    task = tasks[task_id]
    task['status'] = 'processing'
    
    for i, row in enumerate(rows):
        if task['stop_event'].is_set():
            task['status'] = 'stopped'
            return

        row_id = row.get('id', 'N/A')
        img_link = row.get('image_link', '')
        
        if not img_link:
            task['results'].append({'id': row_id, 'image_link': img_link, 'text_extracted': 'No link', 'status': 'failed'})
        else:
            temp_file = download_image(img_link)
            if temp_file:
                text, _ = extract_text_from_file(temp_file)
                task['results'].append({'id': row_id, 'image_link': img_link, 'text_extracted': text, 'status': 'success'})
                try: os.remove(temp_file)
                except: pass
            else:
                task['results'].append({'id': row_id, 'image_link': img_link, 'text_extracted': 'Download failed', 'status': 'failed'})
        
        task['progress'] = i + 1
        
    task['status'] = 'completed'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    source_type = request.form.get('source_type')
    temp_file = None
    try:
        if source_type == 'url':
            url = request.form.get('url')
            temp_file = download_image(url)
            if not temp_file: return jsonify({'error': 'Failed to download image'}), 400
        elif source_type == 'file':
            file = request.files.get('file')
            if not file: return jsonify({'error': 'No file'}), 400
            ext = file.filename.split('.')[-1]
            temp_file = os.path.join(app.config['UPLOAD_FOLDER'], f"tmp_single_{uuid.uuid4().hex}.{ext}")
            file.save(temp_file)
        else: return jsonify({'error': 'Invalid source'}), 400
        
        text, engine = extract_text_from_file(temp_file)
        return jsonify({'success': True, 'text': text, 'engine': engine})
    finally:
        if temp_file and os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass

@app.route('/api/bulk-upload', methods=['POST'])
def bulk_upload():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'): return jsonify({'error': 'Not a CSV'}), 400
    
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        rows = list(reader)
        
        if 'image_link' not in reader.fieldnames:
            return jsonify({'error': 'CSV must have "image_link" column'}), 400
            
        task_id = str(uuid.uuid4())
        tasks[task_id] = {
            'progress': 0,
            'total': len(rows),
            'results': [],
            'status': 'pending',
            'stop_event': threading.Event()
        }
        
        thread = threading.Thread(target=process_bulk_csv, args=(task_id, rows))
        thread.start()
        
        return jsonify({'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/task-status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'progress': task['progress'],
        'total': task['total'],
        'status': task['status'],
        'percent': int((task['progress'] / task['total']) * 100) if task['total'] > 0 else 0
    })

@app.route('/api/task-stop/<task_id>', methods=['POST'])
def task_stop(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({'error': 'Not found'}), 404
    task['stop_event'].set()
    return jsonify({'success': True})

@app.route('/api/task-download/<task_id>')
def task_download(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({'error': 'Not found'}), 404
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['id', 'image_link', 'text_extracted', 'status'])
    writer.writeheader()
    writer.writerows(task['results'])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'results_{task_id[:8]}.csv'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)
