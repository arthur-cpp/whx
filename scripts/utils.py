#!/usr/bin/env python3
"""
Utility functions for speaker profile management.
Used by optional scripts (list_speakers.sh, delete_speaker.sh).
"""

import json
import os
from pathlib import Path
from typing import Dict, List


def get_speakers_dir() -> str:
    """Get the speakers directory path."""
    # Return path relative to project root: ./speakers/data
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    return str(project_root / "speakers" / "data")


def load_speakers_metadata() -> Dict:
    """Load speakers.json metadata."""
    speakers_dir = get_speakers_dir()
    metadata_path = os.path.join(speakers_dir, "speakers.json")

    if not os.path.exists(metadata_path):
        return {}

    with open(metadata_path, 'r') as f:
        return json.load(f)


def save_speakers_metadata(metadata: Dict):
    """Save speakers.json metadata."""
    speakers_dir = get_speakers_dir()
    os.makedirs(speakers_dir, exist_ok=True)

    metadata_path = os.path.join(speakers_dir, "speakers.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


def list_speakers() -> List[Dict]:
    """
    List all registered speakers.

    Returns:
        List of speaker info dicts
    """
    metadata = load_speakers_metadata()

    speakers = []
    for speaker_id, info in metadata.items():
        speakers.append({
            "id": speaker_id,
            "name": info.get("name", speaker_id),
            "created": info.get("created", "unknown"),
            "duration": info.get("duration", 0.0),
            "model": info.get("model", "unknown")
        })

    return sorted(speakers, key=lambda x: x["name"])


def delete_speaker(speaker_id: str) -> bool:
    """
    Delete a speaker profile.

    Args:
        speaker_id: Speaker ID (lowercase, underscores)

    Returns:
        True if deleted, False if not found
    """
    speakers_dir = get_speakers_dir()

    # Delete .npy file
    npy_path = os.path.join(speakers_dir, f"{speaker_id}.npy")
    if os.path.exists(npy_path):
        os.remove(npy_path)
    else:
        return False

    # Update metadata
    metadata = load_speakers_metadata()
    if speaker_id in metadata:
        del metadata[speaker_id]
        save_speakers_metadata(metadata)

    return True


def speaker_exists(speaker_id: str) -> bool:
    """Check if a speaker profile exists."""
    speakers_dir = get_speakers_dir()
    npy_path = os.path.join(speakers_dir, f"{speaker_id}.npy")
    return os.path.exists(npy_path)


if __name__ == "__main__":
    # Simple test/demo
    print("Speakers directory:", get_speakers_dir())
    print("\nRegistered speakers:")

    speakers = list_speakers()
    if speakers:
        for s in speakers:
            print(f"  - {s['name']} (ID: {s['id']}, created: {s['created']})")
    else:
        print("  (none)")
