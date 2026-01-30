#!/usr/bin/env python3
"""
Extract speaker embedding from audio file using pyannote.audio.
Creates a speaker profile (.npy) and updates metadata.
"""

import argparse
import json
import numpy as np
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import torch

    # Fix for PyTorch 2.6+ weights_only=True default
    # Since pyannote.audio models from HuggingFace are trusted, we use weights_only=False
    # This is simpler and more reliable than trying to allowlist all classes
    _original_torch_load = torch.load
    def _patched_torch_load(f, map_location=None, pickle_module=None, *, weights_only=None, mmap=None, **pickle_load_args):
        # Force weights_only to False for compatibility with pyannote models
        return _original_torch_load(f, map_location=map_location, pickle_module=pickle_module,
                                    weights_only=False, mmap=mmap, **pickle_load_args)
    torch.load = _patched_torch_load

    from pyannote.audio import Inference
except ImportError:
    print("ERROR: pyannote.audio not installed. Run: pip install pyannote.audio", file=sys.stderr)
    sys.exit(1)


def extract_embedding(audio_path: str, hf_token: str = None) -> np.ndarray:
    """
    Extract speaker embedding from audio file.

    Args:
        audio_path: Path to audio file (16kHz mono WAV)
        hf_token: HuggingFace token for pyannote model access

    Returns:
        NumPy array with speaker embedding (512-dim)
    """
    # Load pyannote embedding model
    model = Inference(
        "pyannote/embedding",
        use_auth_token=hf_token or os.environ.get("HF_TOKEN")
    )

    # Extract embedding from entire audio
    # The model returns embeddings for the entire file or segments
    embedding = model(audio_path)

    # Handle different return types from pyannote.audio
    # In newer versions, it returns pyannote.core.SlidingWindowFeature
    if hasattr(embedding, 'data'):
        # SlidingWindowFeature object - extract the data array
        embedding_data = embedding.data
        if isinstance(embedding_data, np.ndarray):
            # Average across time dimension if multi-dimensional
            if embedding_data.ndim > 1:
                embedding = np.mean(embedding_data, axis=0)
            else:
                embedding = embedding_data
        elif torch.is_tensor(embedding_data):
            if embedding_data.ndim > 1:
                embedding = torch.mean(embedding_data, dim=0).cpu().numpy()
            else:
                embedding = embedding_data.cpu().numpy()
    elif isinstance(embedding, np.ndarray):
        # Direct numpy array
        if embedding.ndim > 1:
            embedding = np.mean(embedding, axis=0)
    elif torch.is_tensor(embedding):
        # Direct torch tensor
        if embedding.ndim > 1:
            embedding = torch.mean(embedding, dim=0).cpu().numpy()
        else:
            embedding = embedding.cpu().numpy()

    return embedding


def update_metadata(metadata_path: str, speaker_id: str, speaker_name: str,
                    audio_file: str, duration: float, embedding_dim: int):
    """
    Update speakers.json with new speaker profile metadata.

    Args:
        metadata_path: Path to speakers.json
        speaker_id: Speaker ID (lowercase, underscores)
        speaker_name: Display name
        audio_file: Original audio file path
        duration: Audio duration in seconds
        embedding_dim: Embedding dimension
    """
    # Load existing metadata
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}

    # Add/update speaker entry
    # audio_file is passed as-is (can be relative or absolute)
    metadata[speaker_id] = {
        "name": speaker_name,
        "created": datetime.utcnow().isoformat() + "Z",
        "audio_file": audio_file,
        "duration": round(duration, 2),
        "embedding_dim": embedding_dim,
        "model": "pyannote/embedding"
    }

    # Save metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def main():
    parser = argparse.ArgumentParser(description="Extract speaker embedding from audio")
    parser.add_argument("--input", required=True, help="Input audio file (16kHz mono WAV)")
    parser.add_argument("--output", required=True, help="Output .npy file path")
    parser.add_argument("--speaker_name", required=True, help="Speaker display name")
    parser.add_argument("--metadata", required=True, help="Path to speakers.json")
    parser.add_argument("--hf_token", help="HuggingFace token (or use HF_TOKEN env)")
    parser.add_argument("--original_audio", help="Original audio file path (for metadata)")

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Extract embedding
    print("Extracting speaker embedding...")
    try:
        embedding = extract_embedding(args.input, args.hf_token)
    except Exception as e:
        print(f"ERROR: Failed to extract embedding: {e}", file=sys.stderr)
        print("\nMake sure you have:", file=sys.stderr)
        print("1. Accepted the pyannote/embedding license at https://huggingface.co/pyannote/embedding", file=sys.stderr)
        print("2. Set HF_TOKEN with read access to the model", file=sys.stderr)
        sys.exit(1)

    # Save embedding
    np.save(args.output, embedding)
    print(f"Saved embedding: {args.output} (shape: {embedding.shape})")

    # Update metadata
    speaker_id = Path(args.output).stem
    duration = get_audio_duration(args.input)

    # Use original_audio path for metadata if provided, otherwise use input
    audio_file_for_metadata = args.original_audio if args.original_audio else args.input

    update_metadata(
        args.metadata,
        speaker_id,
        args.speaker_name,
        audio_file_for_metadata,
        duration,
        len(embedding)
    )
    print(f"Updated metadata: {args.metadata}")


if __name__ == "__main__":
    main()
