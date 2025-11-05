from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import csv
import io
from pipeline import run
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
    # Token is already loaded by setup_environment() above
    # Just check and warn if still not set
    if not os.environ.get('HF_TOKEN') and not os.environ.get('MISTRAL_API_KEY'):
        print("\n" + "="*60)
        print("⚠ WARNING: HF_TOKEN or MISTRAL_API_KEY not set!")
        print("="*60)
        print("Create a token.md file with your token:")
        print('  $env:HF_TOKEN = "your_token_here"')
        print("\nOr create a .env file:")
        print('  HF_TOKEN=your_token_here')
        print("="*60 + "\n")
    
    port = int(os.environ.get('PORT', 5010))
    print(f"\n🚀 Starting Flask server on http://localhost:{port}")
    print("📱 Open http://localhost:5010 in your browser\n")
    app.run(debug=True, host='0.0.0.0', port=port)

