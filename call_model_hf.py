import os
import requests
import json

MODEL = "mistralai/Mistral-7B-Instruct-v0.2"  # <--- replace with correct model id or mixtral id

# Global variables for local model
_local_model = None
_local_tokenizer = None
_model_loaded = False

def get_local_model_path():
    """Get the path to the local model directory"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_index = os.path.join(current_dir, "model.safetensors.index.json")
    if os.path.exists(model_index):
        return current_dir
    return None

def load_local_model():
    """Load the local Mistral model from disk"""
    global _local_model, _local_tokenizer, _model_loaded
    
    if _model_loaded:
        return _local_model, _local_tokenizer
    
    try:
        model_path = get_local_model_path()
        if not model_path:
            return None, None
        
        print(f"Loading local model from: {model_path}")
        
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        
        _local_tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        print("Loading model... (this may take a few minutes)")
        _local_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map="auto",
            local_files_only=True
        )
        
        _model_loaded = True
        print("✅ Local model loaded successfully!")
        return _local_model, _local_tokenizer
        
    except Exception as e:
        print(f"Error loading local model: {e}")
        return None, None

def call_local_model(prompt: str, max_new_tokens: int = 4096, temperature: float = 0.0):
    """Call the local Mistral model directly (no API needed)"""
    global _local_model, _local_tokenizer
    
    if not _model_loaded:
        model, tokenizer = load_local_model()
        if model is None or tokenizer is None:
            raise ValueError("Local model could not be loaded")
    
    try:
        import torch
        
        # Format prompt using chat template if available
        if hasattr(_local_tokenizer, 'apply_chat_template') and _local_tokenizer.chat_template:
            messages = [{"role": "user", "content": prompt}]
            formatted_prompt = _local_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            formatted_prompt = f"[INST] {prompt} [/INST]"
        
        inputs = _local_tokenizer(formatted_prompt, return_tensors="pt")
        device = next(_local_model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = _local_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=(temperature > 0),
                pad_token_id=_local_tokenizer.eos_token_id
            )
        
        generated_text = _local_tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        return generated_text.strip()
        
    except Exception as e:
        raise Exception(f"Error calling local model: {e}")

def get_hf_token():
    """Get HF_TOKEN from environment (reads dynamically)"""
    return os.environ.get("HF_TOKEN")

def get_mistral_api_key():
    """Get MISTRAL_API_KEY from environment (reads dynamically, falls back to HF_TOKEN)"""
    return os.environ.get("MISTRAL_API_KEY") or os.environ.get("HF_TOKEN")

def call_mistral_api(prompt: str, max_retries: int = 3):
    """
    Call Mistral API directly.
    
    Args:
        prompt: The prompt to send to the model
        max_retries: Maximum number of retry attempts
    
    Returns:
        dict: Response from the API
    """
    import time
    mistral_key = get_mistral_api_key()
    if not mistral_key:
        raise ValueError("MISTRAL_API_KEY or HF_TOKEN environment variable is not set.")
    
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {mistral_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-medium",  # or "mistral-small", "mistral-large"
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 4096  # Increased for long custom fields (offers, descriptions, etc.)
    }
    
    for attempt in range(max_retries):
        try:
            # Use longer timeout for large prompts (30s connect, 180s read)
            # Large prompts (18k+ chars) may take 2-3 minutes to process
            timeout_duration = (30, 180)  # (connect timeout, read timeout)
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_duration)
            
            # Check for rate limit (429)
            if r.status_code == 429:
                retry_after = int(r.headers.get('Retry-After', 60))  # Default 60 seconds if header not present
                if attempt < max_retries - 1:
                    wait_time = max(retry_after, 60)  # Wait at least 60 seconds for rate limit
                    print(f"⚠️  Rate limit exceeded (429). Waiting {wait_time} seconds before retry... (attempt {attempt + 1}/{max_retries})")
                    print(f"💡 Tip: Mistral API has rate limits. Consider upgrading your plan or waiting longer.")
                    time.sleep(wait_time)
                    continue
                else:
                    # Create proper HTTPError with response
                    from requests.exceptions import HTTPError
                    error_msg = (
                        f"429 Too Many Requests: Rate limit exceeded. Please wait {retry_after} seconds before trying again. "
                        f"Or upgrade your Mistral API plan for higher limits."
                    )
                    http_error = HTTPError(error_msg)
                    http_error.response = r
                    raise http_error
            
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            # Rate limit already handled above, but check here too for safety
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                raise  # Re-raise rate limit errors (should already be handled above)
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Request failed, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise
        except requests.exceptions.Timeout as e:
            # Handle timeout specifically - large prompts may need more time
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⏱️  Request timeout - API is taking too long to respond (large prompt: {len(prompt)} chars)")
                print(f"   Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                print(f"   💡 Tip: This can happen with large prompts. Consider using shorter text or waiting.")
                time.sleep(wait_time)
            else:
                raise requests.exceptions.Timeout(
                    f"Request timed out after 180 seconds. The prompt is very large ({len(prompt)} characters).\n"
                    f"💡 Solutions:\n"
                    f"   1. Wait a moment and try again (API may be experiencing high load)\n"
                    f"   2. Consider using a smaller/faster model (e.g., mistral-small instead of mistral-medium)\n"
                    f"   3. Reduce the input text size if possible"
                ) from e
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Request failed, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise

def call_hf_inference(prompt: str, model: str = MODEL, max_retries: int = 3, use_mistral_api=False):
    """
    Call local model, Hugging Face Inference API, or Mistral API with retry logic.
    Priority: 1) Local model (if available) 2) Mistral API 3) HF API
    
    Args:
        prompt: The prompt to send to the model
        model: Model ID to use (for HF API)
        max_retries: Maximum number of retry attempts
        use_mistral_api: If True, use Mistral API directly instead of HF
    
    Returns:
        dict: Response from the model/API
    """
    # FIRST: Try local model if available
    model_path = get_local_model_path()
    if model_path:
        try:
            print("Using local model (trying first)...")
            generated_text = call_local_model(prompt, max_new_tokens=4096, temperature=0.0)
            return {"generated_text": generated_text}
        except Exception as e:
            print(f"Local model failed: {e}")
            print("Falling back to API...")
    
    # If local model not available or failed, use API
    # Get tokens for API fallback
    mistral_key = get_mistral_api_key()
    hf_token = get_hf_token()
    
    # Try Mistral API first if key format suggests it or explicitly requested
    if use_mistral_api or (mistral_key and not mistral_key.startswith("hf_")):
        try:
            return call_mistral_api(prompt, max_retries)
        except requests.exceptions.HTTPError as e:
            # Check if it's a rate limit error (429) - don't fallback to HF if we don't have valid HF token
            if e.response and e.response.status_code == 429:
                # Only try HF if we have a valid HF token
                if hf_token and hf_token.startswith("hf_"):
                    print(f"Mistral API rate limit exceeded. Falling back to HuggingFace API...")
                else:
                    # No valid HF token, re-raise the rate limit error with helpful message
                    error_msg = (
                        f"429 Too Many Requests: Mistral API rate limit exceeded.\n"
                        f"💡 Solutions:\n"
                        f"   1. Wait a few minutes and try again\n"
                        f"   2. Upgrade your Mistral API plan for higher rate limits\n"
                        f"   3. Set a valid HF_TOKEN (starting with 'hf_') to use HuggingFace API as fallback"
                    )
                    http_error = requests.exceptions.HTTPError(error_msg)
                    http_error.response = e.response
                    raise http_error from e
            elif e.response and e.response.status_code == 401:
                # Authentication error - don't try HF fallback
                error_msg = (
                    f"401 Unauthorized: Invalid Mistral API key.\n"
                    f"💡 Please check your MISTRAL_API_KEY in token.md or environment variables."
                )
                http_error = requests.exceptions.HTTPError(error_msg)
                http_error.response = e.response
                raise http_error from e
            else:
                # Other errors - try HF if we have valid token
                if hf_token and hf_token.startswith("hf_"):
                    print(f"Mistral API call failed: {e}, trying HF API...")
                else:
                    raise  # Re-raise if no valid HF token
    
    # Check if we have a valid HF token before trying HF API
    # If token doesn't start with "hf_", try it anyway (might be a different HF token format)
    if not hf_token:
        raise ValueError(
            "HF_TOKEN not set or invalid.\n"
            "💡 To use HuggingFace API, set a valid token:\n"
            "   - Windows PowerShell: $env:HF_TOKEN = 'your_token'\n"
            "   - Or add to token.md: $env:HF_TOKEN = 'your_token'\n"
        )
    
    # Try HF API even if token doesn't start with "hf_" (some tokens might have different format)
    if not hf_token.startswith("hf_"):
        print(f"⚠ Note: Token doesn't start with 'hf_' - trying HuggingFace API anyway...")
    
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 4096, "temperature": 0.0}}  # Increased for long custom fields
    
    for attempt in range(max_retries):
        try:
            # Increased timeout for large prompts
            r = requests.post(url, headers=headers, json=payload, timeout=(30, 120))
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # exponential backoff
                print(f"Request failed, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                import time
                time.sleep(wait_time)
            else:
                raise

def extract_json_from_response(resp, is_mistral=False, is_local=False):
    """
    Extract JSON from API response (Hugging Face, Mistral, or local model).
    
    Args:
        resp: Response from API or local model
        is_mistral: Whether this is a Mistral API response
        is_local: Whether this is from local model
    
    Returns:
        str: Extracted text from the response
    """
    if is_local:
        if isinstance(resp, dict):
            return resp.get("generated_text", str(resp))
        return str(resp)
    elif is_mistral:
        # Mistral API response format
        if isinstance(resp, dict):
            choices = resp.get("choices", [])
            if choices and len(choices) > 0:
                generated = choices[0].get("message", {}).get("content", "")
                return generated
        return str(resp)
    else:
        # Hugging Face API response format
        if isinstance(resp, list):
            if len(resp) > 0:
                if isinstance(resp[0], dict):
                    generated = resp[0].get("generated_text") or resp[0].get("text") or str(resp[0])
                else:
                    generated = str(resp[0])
            else:
                generated = str(resp)
        elif isinstance(resp, dict):
            generated = resp.get("generated_text") or resp.get("text") or str(resp)
        else:
            generated = str(resp)
        return generated

if __name__ == "__main__":
    # Example prompt
    prompt = """You are given raw text extracted from a product web page (OCR). Extract the main customer review and the rating for that review. Return ONLY a single JSON object with keys:
- rating: a number from 0 to 5 or null if not present
- review: the review text or null if not present
- source: "ocr" or "dom" (where text came from)

If multiple ratings/reviews are present, return the most prominent review (e.g., topmost review). If none found, set rating and review to null.

Example input:
Product: T-Shirt
Price: ₹299
Customer Review: "Great quality, fits well"
Rating: 4.5/5

Output (exact JSON):
{"rating": 4.5, "review": "Great quality, fits well", "source": "ocr"}
"""
    
    try:
        resp = call_hf_inference(prompt)
        generated = extract_json_from_response(resp)
        print("Response:", generated)
    except Exception as e:
        print(f"Error: {e}")

