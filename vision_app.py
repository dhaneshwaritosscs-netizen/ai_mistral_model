import os
import uuid
import base64
import requests
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI() # Expects OPENAI_API_KEY in environment

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads_vision'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def extract_text_vision(image_source, is_url=True):
    prompt = """
    Extract all readable text from this image. 
    Only output meaningful English text (A-Z, a-z, numbers, and basic punctuation).
    Ignore garbage characters, symbols, unreadable strings, or non-English characters completely.
    If the image contains no readable English text, return "No text found".
    Do not include any extra explanation, comments, or markdown formatting (output raw text only).
    """
    
    try:
        content = [{"type": "text", "text": prompt}]
        
        if is_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_source}
            })
        else:
            base64_image = encode_image(image_source)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/')
def index():
    return render_template('vision_index.html')

@app.route('/extract', methods=['POST'])
def extract():
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        return jsonify({'error': 'OPENAI_API_KEY is not set on the server.'}), 500

    temp_file = None
    try:
        source_type = request.form.get('source_type')
        
        if source_type == 'url':
            url = request.form.get('url')
            if not url:
                return jsonify({'error': 'No URL provided'}), 400
            result = extract_text_vision(url, is_url=True)
        
        elif source_type == 'file':
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            ext = file.filename.split('.')[-1]
            temp_file = os.path.join(app.config['UPLOAD_FOLDER'], f"tmp_vision_{uuid.uuid4().hex}.{ext}")
            file.save(temp_file)
            result = extract_text_vision(temp_file, is_url=False)
        
        else:
            return jsonify({'error': 'Invalid source type'}), 400
            
        return jsonify({
            'success': True,
            'text': result,
            'engine': 'OpenAI GPT-4o Vision'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

if __name__ == '__main__':
    print("Starting OpenAI Vision OCR App on port 5002...")
    print("Go to http://127.0.0.1:5002")
    app.run(debug=True, port=5002)
