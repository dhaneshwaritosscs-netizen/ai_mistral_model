#!/usr/bin/env python3
"""
Upload model files to Hugging Face Hub.

This script uploads your model files to Hugging Face Hub, which supports
large files (up to 10GB per file) unlike GitHub's 2GB limit.

Requirements:
    pip install huggingface_hub

Usage:
    python upload_to_hf.py --repo-id your-username/your-model-name
"""

import os
import argparse
from pathlib import Path
from huggingface_hub import HfApi, create_repo, login
from huggingface_hub.utils import HfFolder

def upload_model_to_hf(repo_id: str, local_dir: str = ".", token: str = None):
    """
    Upload model files to Hugging Face Hub.
    
    Args:
        repo_id: Repository ID in format "username/repo-name"
        local_dir: Local directory containing model files
        token: Hugging Face token (if None, will use environment or prompt)
    """
    # Get token
    if token:
        os.environ["HF_TOKEN"] = token
    elif not os.environ.get("HF_TOKEN") and not HfFolder.get_token():
        token = input("Enter your Hugging Face token (or set HF_TOKEN env var): ").strip()
        if token:
            login(token=token)
        else:
            raise ValueError("HF_TOKEN is required. Set it as environment variable or pass --token")
    
    api = HfApi()
    
    # Create repository if it doesn't exist
    try:
        create_repo(repo_id=repo_id, exist_ok=True, repo_type="model")
        print(f"✅ Repository '{repo_id}' is ready")
    except Exception as e:
        print(f"⚠️  Note: {e}")
    
    local_path = Path(local_dir)
    
    # Files to upload (model files and config)
    model_files = [
        "consolidated.safetensors",
        "model-00001-of-00003.safetensors",
        "model-00002-of-00003.safetensors",
        "model-00003-of-00003.safetensors",
        "model.safetensors.index.json",
        "params.json",
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer.model.v3",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "generation_config.json",
        "config.json",
    ]
    
    files_to_upload = []
    for file_name in model_files:
        file_path = local_path / file_name
        if file_path.exists():
            files_to_upload.append(str(file_path))
            size_gb = file_path.stat().st_size / (1024**3)
            print(f"📦 Found: {file_name} ({size_gb:.2f} GB)")
        else:
            print(f"⚠️  Missing: {file_name}")
    
    if not files_to_upload:
        print("❌ No model files found to upload!")
        return
    
    print(f"\n🚀 Uploading {len(files_to_upload)} files to '{repo_id}'...")
    print("   This may take a while for large files...\n")
    
    # Upload files
    try:
        api.upload_folder(
            folder_path=local_dir,
            repo_id=repo_id,
            repo_type="model",
            allow_patterns=model_files,
            ignore_patterns=["*.py", "*.pyc", "__pycache__", "*.png", "*.jpg", "*.jpeg", "tmp_*"],
        )
        print(f"\n✅ Successfully uploaded model to: https://huggingface.co/{repo_id}")
        print(f"\n💡 To use the model, others can download it with:")
        print(f"   from huggingface_hub import snapshot_download")
        print(f"   snapshot_download(repo_id='{repo_id}')")
    except Exception as e:
        print(f"\n❌ Error uploading: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload model files to Hugging Face Hub"
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        required=True,
        help="Repository ID in format 'username/repo-name' (e.g., 'your-username/your-model-name')"
    )
    parser.add_argument(
        "--local-dir",
        type=str,
        default=".",
        help="Local directory containing model files (default: current directory)"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Hugging Face token (or set HF_TOKEN environment variable)"
    )
    
    args = parser.parse_args()
    
    upload_model_to_hf(
        repo_id=args.repo_id,
        local_dir=args.local_dir,
        token=args.token
    )

