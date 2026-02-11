"""
Configuration loader - automatically loads API tokens from files
"""
import os
import re

def load_token_from_file():
    """
    Try to load HF_TOKEN or MISTRAL_API_KEY from token.md or .env file
    Returns the token if found, None otherwise
    """
    print("DEBUG: Attempting to load token...")
    
    token = None
    
    # Try to read from token.md file
    try:
        if os.path.exists('token.md'):
            with open('token.md', 'r') as f:
                content = f.read()
                # Look for HF_TOKEN or MISTRAL_API_KEY pattern
                # Match: $env:HF_TOKEN = "token" or set HF_TOKEN=token or export HF_TOKEN="token"
                patterns = [
                    r'\$env:HF_TOKEN\s*=\s*["\']([^"\']+)["\']',  # PowerShell format: $env:HF_TOKEN = "token"
                    r'HF_TOKEN\s*[=:]\s*["\']?([^"\'\s\n]+)["\']?',  # Standard format
                    r'MISTRAL_API_KEY\s*[=:]\s*["\']?([^"\'\s\n]+)["\']?',  # Mistral format
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        token = match.group(1)
                        break
    except Exception as e:
        print(f"Warning: Could not read token.md: {e}")
    
    # Try to read from .env file
    if not token:
        try:
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('#') or not line:
                            continue
                        # Match: HF_TOKEN=token or MISTRAL_API_KEY=token
                        if 'HF_TOKEN' in line.upper() or 'MISTRAL_API_KEY' in line.upper():
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                token = parts[1].strip().strip('"').strip("'")
                                break
        except Exception as e:
            print(f"Warning: Could not read .env: {e}")
    
    return token

def setup_environment():
    """
    Setup environment variables from config files if not already set
    """
    # If token already set in environment, don't override
    print("DEBUG: Checking existing environment variables...")
    if os.environ.get('HF_TOKEN'):
        print(f"DEBUG: Found HF_TOKEN in environment: {os.environ.get('HF_TOKEN')[:4]}...")
    if os.environ.get('MISTRAL_API_KEY'):
        print(f"DEBUG: Found MISTRAL_API_KEY in environment: {os.environ.get('MISTRAL_API_KEY')[:4]}...")
    
    if os.environ.get('HF_TOKEN') or os.environ.get('MISTRAL_API_KEY'):
        return
    
    print("DEBUG: Looking for token in files...")
    token = load_token_from_file()
    if token:
        print(f"DEBUG: Found token: {token[:4]}...")
        # Determine if it's HF token (starts with hf_) or Mistral token
        if token.startswith('hf_'):
            os.environ['HF_TOKEN'] = token
            print(f"[OK] Loaded HF_TOKEN from config file")
        else:
            os.environ['MISTRAL_API_KEY'] = token
            os.environ['HF_TOKEN'] = token  # Also set HF_TOKEN for compatibility
            print(f"[OK] Loaded MISTRAL_API_KEY from config file")
        print(f"DEBUG: Token source: {token}")
    else:
        print("[WARN] Warning: No token found in token.md or .env file")
        print("   Please set HF_TOKEN or MISTRAL_API_KEY environment variable")

