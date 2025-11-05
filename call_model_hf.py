import os
import requests
import json

MODEL = "mistralai/Mistral-7B-Instruct-v0.2"  # <--- replace with correct model id or mixtral id

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
    Call Hugging Face Inference API or Mistral API with retry logic.
    
    Args:
        prompt: The prompt to send to the model
        model: Model ID to use (for HF API)
        max_retries: Maximum number of retry attempts
        use_mistral_api: If True, use Mistral API directly instead of HF
    
    Returns:
        dict: Response from the API
    """
    # Get tokens dynamically
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
    if not hf_token or not hf_token.startswith("hf_"):
        raise ValueError(
            "HF_TOKEN not set or invalid.\n"
            "💡 To use HuggingFace API, set a valid token (starts with 'hf_'):\n"
            "   - Windows PowerShell: $env:HF_TOKEN = 'hf_...'\n"
            "   - Or add to token.md: $env:HF_TOKEN = 'hf_...'\n"
            "💡 Your current token appears to be a Mistral API key (not HF token)."
        )
    
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

def extract_json_from_response(resp, is_mistral=False):
    """
    Extract JSON from API response (Hugging Face or Mistral).
    
    Args:
        resp: Response from API
        is_mistral: Whether this is a Mistral API response
    
    Returns:
        str: Extracted text from the response
    """
    if is_mistral:
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

