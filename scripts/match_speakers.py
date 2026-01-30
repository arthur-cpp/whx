#!/usr/bin/env python3
"""
Match WhisperX speaker labels (SPEAKER_00, SPEAKER_01, etc.) with known speaker profiles.
Also handles fallback: convert JSON to TXT when no profiles are available.
"""

import argparse
import json
import numpy as np
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import torch
    from pyannote.core import Segment

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


def load_speaker_profiles(speakers_dir: str) -> Dict[str, np.ndarray]:
    """
    Load all speaker profiles from ~/.whx/speakers/

    Returns:
        Dict mapping speaker_id to embedding vector
    """
    profiles = {}

    if not os.path.exists(speakers_dir):
        return profiles

    # Load metadata to get proper names
    metadata_path = os.path.join(speakers_dir, "speakers.json")
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

    # Load all .npy files
    for npy_file in Path(speakers_dir).glob("*.npy"):
        speaker_id = npy_file.stem
        embedding = np.load(npy_file)

        # Get display name from metadata
        if speaker_id in metadata:
            display_name = metadata[speaker_id]["name"]
        else:
            display_name = speaker_id.replace("_", " ").title()

        profiles[display_name] = embedding

    return profiles


def extract_speaker_segments(json_data: dict, speaker_label: str) -> List[Tuple[float, float]]:
    """
    Extract time segments for a specific speaker from WhisperX JSON.

    Returns:
        List of (start, end) tuples in seconds
    """
    segments = []

    for segment in json_data.get("segments", []):
        if segment.get("speaker") == speaker_label:
            start = segment.get("start", 0.0)
            end = segment.get("end", 0.0)
            duration = end - start

            # Only use segments longer than 2 seconds for better quality
            if duration >= 2.0:
                segments.append((start, end))

    return segments


def extract_embedding_for_speaker(audio_path: str, segments: List[Tuple[float, float]],
                                  hf_token: str = None, max_segments: int = 10) -> np.ndarray:
    """
    Extract and average embeddings for a speaker from their audio segments.

    Args:
        audio_path: Path to audio file
        segments: List of (start, end) time segments
        hf_token: HuggingFace token
        max_segments: Maximum segments to process (for performance)

    Returns:
        Averaged embedding vector
    """
    if not segments:
        return None

    # Load pyannote model
    model = Inference(
        "pyannote/embedding",
        use_auth_token=hf_token or os.environ.get("HF_TOKEN")
    )

    embeddings = []

    # Process up to max_segments (sorted by duration, longest first)
    segments_sorted = sorted(segments, key=lambda x: x[1] - x[0], reverse=True)
    segments_to_process = segments_sorted[:max_segments]

    for start, end in segments_to_process:
        try:
            # Extract embedding for this segment
            # pyannote Inference accepts file paths and can extract excerpts
            excerpt = Segment(start=start, end=end)
            embedding = model.crop(audio_path, excerpt)

            # Handle different return types from pyannote.audio
            # In newer versions (3.x), it returns SlidingWindowFeature wrapper
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
                # Direct numpy array (older pyannote versions)
                if embedding.ndim > 1:
                    embedding = np.mean(embedding, axis=0)
            elif torch.is_tensor(embedding):
                # Direct torch tensor (older pyannote versions)
                if embedding.ndim > 1:
                    embedding = torch.mean(embedding, dim=0).cpu().numpy()
                else:
                    embedding = embedding.cpu().numpy()

            embeddings.append(embedding)
        except Exception as e:
            print(f"Warning: Failed to extract segment [{start:.2f}-{end:.2f}]: {e}", file=sys.stderr)
            continue

    if not embeddings:
        return None

    # Average all embeddings
    return np.mean(embeddings, axis=0)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def match_speakers(json_data: dict, audio_path: str, profiles: Dict[str, np.ndarray],
                   threshold: float = 0.75, hf_token: str = None) -> Dict[str, str]:
    """
    Match SPEAKER_XX labels to known speaker profiles.

    Returns:
        Dict mapping SPEAKER_XX -> display name (or SPEAKER_XX if no match)
    """
    mapping = {}

    # Get unique speakers from JSON
    speakers = set()
    for segment in json_data.get("segments", []):
        speaker = segment.get("speaker")
        if speaker:
            speakers.add(speaker)

    print(f"Found {len(speakers)} speaker(s) in transcription: {sorted(speakers)}")

    if not profiles:
        print("No speaker profiles available for matching")
        return {s: s for s in speakers}  # Return identity mapping

    print(f"Loaded {len(profiles)} speaker profile(s): {list(profiles.keys())}")

    # For each speaker in transcription, extract their embedding
    for speaker_label in sorted(speakers):
        print(f"\nProcessing {speaker_label}...")

        # Get segments for this speaker
        segments = extract_speaker_segments(json_data, speaker_label)
        print(f"  Found {len(segments)} segments (>2s)")

        if not segments:
            mapping[speaker_label] = speaker_label
            continue

        # Extract embedding for this speaker
        try:
            speaker_embedding = extract_embedding_for_speaker(
                audio_path, segments, hf_token, max_segments=10
            )
        except Exception as e:
            print(f"  ERROR: Failed to extract embedding: {e}", file=sys.stderr)
            mapping[speaker_label] = speaker_label
            continue

        if speaker_embedding is None:
            mapping[speaker_label] = speaker_label
            continue

        # Compare with all known profiles
        best_match = None
        best_score = -1.0

        for profile_name, profile_embedding in profiles.items():
            similarity = cosine_similarity(speaker_embedding, profile_embedding)
            print(f"  Similarity with '{profile_name}': {similarity:.4f}")

            if similarity > best_score:
                best_score = similarity
                best_match = profile_name

        # Apply threshold
        if best_score >= threshold:
            mapping[speaker_label] = best_match
            print(f"  ✓ Matched to: {best_match} (score: {best_score:.4f})")
        else:
            mapping[speaker_label] = speaker_label
            print(f"  ✗ No match (best score {best_score:.4f} < threshold {threshold})")

    return mapping


def apply_speaker_mapping(json_data: dict, mapping: Dict[str, str]) -> dict:
    """Apply speaker name mapping to JSON segments."""
    for segment in json_data.get("segments", []):
        old_speaker = segment.get("speaker")
        if old_speaker and old_speaker in mapping:
            segment["speaker"] = mapping[old_speaker]

    return json_data


def build_speaker_header_mapping(original_mapping: Dict[str, str]) -> Dict[str, str]:
    """
    Build speaker mapping for header display.

    Takes the mapping from match_speakers() and enhances it for display:
    - Matched speakers: "SPEAKER_00" -> "Arthur" (kept as-is)
    - Unmatched speakers: "SPEAKER_03" -> "SPEAKER_03" becomes "SPEAKER_03" -> "[Not Matched]"
    - Unknown speakers: "UNKNOWN" -> "UNKNOWN" becomes "UNKNOWN" -> "[Unknown Speaker]"

    Args:
        original_mapping: Mapping from match_speakers() (SPEAKER_XX -> name or SPEAKER_XX)

    Returns:
        Enhanced mapping for header display
    """
    header_mapping = {}

    for original_label, final_name in original_mapping.items():
        if original_label == "UNKNOWN":
            header_mapping[original_label] = "[Unknown Speaker]"
        elif original_label == final_name:
            # No match found - label stayed the same
            if original_label.startswith("SPEAKER_"):
                header_mapping[original_label] = "[Not Matched]"
            else:
                # Edge case: non-SPEAKER label that stayed the same
                header_mapping[original_label] = final_name
        else:
            # Successfully matched
            header_mapping[original_label] = final_name

    return header_mapping


def generate_txt_output(json_data: dict, output_path: str, speaker_mapping: Optional[Dict[str, str]] = None):
    """
    Convert WhisperX JSON to TXT format with speaker labels and mapping header.

    Format:
        ## Speaker Mapping:
        - SPEAKER_00 → Arthur
        - SPEAKER_01 → Valerian
        - SPEAKER_03 → [Not Matched]

        ---

        [MM:SS.ms] Speaker Name: Text here.
    """
    lines = []

    # Generate speaker mapping header if mapping was provided
    if speaker_mapping:
        lines.append("## Speaker Mapping:")
        for original_label, final_name in sorted(speaker_mapping.items()):
            lines.append(f"- {original_label} → {final_name}")
        lines.append("")  # Blank line
        lines.append("---")
        lines.append("")  # Blank line

    # Generate transcript
    for segment in json_data.get("segments", []):
        start = segment.get("start", 0.0)
        text = segment.get("text", "").strip()
        speaker = segment.get("speaker", "UNKNOWN")

        # Format timestamp as [MM:SS.ms]
        minutes = int(start // 60)
        seconds = start % 60
        timestamp = f"[{minutes:02d}:{seconds:05.2f}]"

        # Format line
        line = f"{timestamp} {speaker}: {text}"
        lines.append(line)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\nGenerated transcript: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Match speakers and generate TXT output")
    parser.add_argument("--json", required=True, help="WhisperX JSON output file")
    parser.add_argument("--audio", required=True, help="Normalized audio file")
    parser.add_argument("--speakers_dir", help="Speaker profiles directory (~/.whx/speakers)")
    parser.add_argument("--threshold", type=float, default=0.75, help="Similarity threshold")
    parser.add_argument("--output_txt", required=True, help="Output TXT file path")
    parser.add_argument("--hf_token", help="HuggingFace token")

    args = parser.parse_args()

    # Load JSON
    if not os.path.exists(args.json):
        print(f"ERROR: JSON file not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    with open(args.json, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # Track speaker mapping for header generation
    speaker_mapping_for_header = None

    # Check if speaker matching is requested
    if args.speakers_dir and os.path.exists(args.speakers_dir):
        # Load profiles
        profiles = load_speaker_profiles(args.speakers_dir)

        if profiles:
            print(f"Speaker matching enabled (threshold: {args.threshold})")

            # Match speakers
            try:
                mapping = match_speakers(
                    json_data,
                    args.audio,
                    profiles,
                    args.threshold,
                    args.hf_token
                )

                # Build header mapping from match results
                speaker_mapping_for_header = build_speaker_header_mapping(mapping)

                # Apply mapping to JSON
                json_data = apply_speaker_mapping(json_data, mapping)

                print(f"\nFinal mapping:")
                for old, new in sorted(mapping.items()):
                    print(f"  {old} -> {new}")
            except Exception as e:
                print(f"ERROR during speaker matching: {e}", file=sys.stderr)
                print("Falling back to SPEAKER_XX labels", file=sys.stderr)

    # Generate TXT output with speaker mapping header
    generate_txt_output(json_data, args.output_txt, speaker_mapping_for_header)


if __name__ == "__main__":
    main()
