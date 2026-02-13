from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import csv
import io
import requests
import uuid
from pipeline import run, run_on_image
from config import setup_environment

# Setup environment variables from config files
setup_environment()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Ensure token is loaded before every request (important for Flask reloader)
@app.before_request
def ensure_token_loaded():
    """Ensure token is loaded before each request"""
    setup_environment()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract_fields():
    """API endpoint to extract fields from a product URL or multiple URLs"""
    try:
        # Ensure token is loaded (in case it wasn't loaded yet)
        setup_environment()
        
        data = request.get_json()
        url = data.get('url')
        urls = data.get('urls', [])
        fields = data.get('fields', [])
        
        # If fields is a string, split by comma
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(',') if f.strip()]
        elif not fields:
            fields = None  # Use default
        
        # Handle multiple URLs
        if urls and len(urls) > 0:
            results = []
            for url_item in urls:
                if url_item and url_item.strip():
                    try:
                        result = run(url_item.strip(), fields=fields)
                        result['url'] = url_item.strip()
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'url': url_item.strip(),
                            'error': str(e),
                            'success': False
                        })
            
            return jsonify({
                'success': True,
                'data': results,
                'count': len(results)
            })
        
        # Handle single URL
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Run the pipeline
        result = run(url, fields=fields)
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/extract/batch', methods=['POST'])
def extract_batch():
    """API endpoint to extract fields from multiple URLs (batch processing)"""
    try:
        setup_environment()
        
        data = request.get_json()
        urls = data.get('urls', [])
        fields = data.get('fields', [])
        
        if not urls or len(urls) == 0:
            return jsonify({'error': 'URLs are required'}), 400
        
        # If fields is a string, split by comma
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(',') if f.strip()]
        elif not fields:
            fields = None
        
        results = []
        for url in urls:
            if url and url.strip():
                try:
                    result = run(url.strip(), fields=fields)
                    result['url'] = url.strip()
                    results.append(result)
                except Exception as e:
                    results.append({
                        'url': url.strip(),
                        'error': str(e),
                        'success': False
                    })
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    """API endpoint to extract fields from URLs in a CSV file"""
    try:
        setup_environment()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV file'}), 400
        
        # Get fields from form data
        fields = request.form.get('fields', '')
        if fields:
            fields = [f.strip() for f in fields.split(',') if f.strip()]
        else:
            fields = None
        
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        
        # Extract URLs from CSV (assuming first column contains URLs)
        urls = []
        for row in csv_reader:
            if row and len(row) > 0 and row[0].strip():
                url = row[0].strip()
                if url.startswith('http://') or url.startswith('https://'):
                    urls.append(url)
        
        if not urls:
            return jsonify({'error': 'No valid URLs found in CSV file'}), 400
        
        # Process all URLs
        results = []
        for url in urls:
            try:
                result = run(url, fields=fields)
                result['url'] = url
                results.append(result)
            except Exception as e:
                results.append({
                    'url': url,
                    'error': str(e),
                    'success': False
                })
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    """API endpoint to extract fields from an uploaded image"""
    try:
        setup_environment()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get fields from form data
        fields = request.form.get('fields', '')
        if fields:
            fields = [f.strip() for f in fields.split(',') if f.strip()]
        else:
            fields = None
            
        # Ensure uploads directory exists
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            
        # Save temporary file

        # Save to temporary file
        temp_filename = f"tmp_{uuid.uuid4().hex}.{file.filename.split('.')[-1]}"
        file.save(temp_filename)
        
        try:
            # Process the image
            # Get fields from form data if available
            fields = request.form.get('fields')
            if fields:
                fields = fields.split(',')
            
            result = run_on_image(temp_filename, fields=fields)
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        # Get extension or default to jpg
        ext = 'jpg'
        if 'content-type' in response.headers:
            ct = response.headers['content-type']
            if 'image/' in ct:
                ext = ct.split('/')[-1]
        
        temp_filename = f"tmp_dl_{uuid.uuid4().hex}.{ext}"
        
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return temp_filename
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
        return None

@app.route('/api/process-image-urls', methods=['POST'])
def process_image_urls():
    """API endpoint to process a CSV of image URLs"""
    try:
        setup_environment()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400

        # Read CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        
        image_urls = []
        for row in csv_reader:
            if row and len(row) > 0 and row[0].strip():
                url = row[0].strip()
                if url.startswith('http'):
                    image_urls.append(url)
        
        if not image_urls:
            return jsonify({'error': 'No valid URLs found in CSV'}), 400
            
        results = []
        fields = request.form.get('fields')
        if fields:
            fields = fields.split(',')

        for url in image_urls:
            try:
                temp_file = download_image(url)
                if temp_file:
                    try:
                        result = run_on_image(temp_file, fields=fields)
                        result['image_url'] = url
                        results.append(result)
                    finally:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                else:
                    results.append({
                        'image_url': url,
                        'error': 'Failed to download image',
                        'success': False
                    })
            except Exception as e:
                results.append({
                    'image_url': url,
                    'error': str(e),
                    'success': False
                })
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/fields', methods=['GET'])
def get_available_fields():
    """Get list of available predefined fields"""
    from pipeline import FIELD_DEFINITIONS
    fields_info = []
    for field_name, field_def in FIELD_DEFINITIONS.items():
        fields_info.append({
            'name': field_name,
            'description': field_def['description'],
            'type': field_def['type'],
            'example': field_def.get('example', '')
        })
    return jsonify({
        'success': True,
        'fields': fields_info
    })

if __name__ == '__main__':
    print("------------------------------------------------------------")
    print("Mistral AI Model Server")
    print("------------------------------------------------------------")
    
    # Check if .env file exists or environment variables are set
    if not os.path.exists('.env') and not os.environ.get('HF_TOKEN'):
        print("WARNING: No .env file found and HF_TOKEN not set in environment.")
        print("Please create a .env file with your Hugging Face token:")
        print("HF_TOKEN=your_token_here")
        print("\nOr create a .env file:")
        print('  HF_TOKEN=your_token_here')
        print("="*60 + "\n")
    
    port = int(os.environ.get('PORT', 5010))
    print(f"\n[OK] Starting Flask server on http://localhost:{port}")
    print("--> Open http://localhost:5010 in your browser\n")
    app.run(debug=True, host='0.0.0.0', port=port)

