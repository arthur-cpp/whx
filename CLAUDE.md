# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**WhisperX Transcription Helper (whx)** is a wrapper script around WhisperX for fast audio/video transcription with word-level timestamps and speaker diarization. The project uses WhisperX (built on faster-whisper) to achieve ~4x speedup over vanilla Whisper while providing better quality, word-level segmentation, and speaker identification. Additionally, it includes **speaker recognition** to automatically match speaker labels with real names.

**Key workflow:** Input media → ffmpeg preprocessing (extract audio, resample to 16kHz mono PCM, normalize loudness) → WhisperX transcription → speaker matching (optional) → output `.txt` transcript next to input file.

## Architecture

### Core Components

1. **`install.sh`** - Installation script that:
   - Creates Python venv at `./venv`
   - Installs whisperx and pyannote.audio packages
   - Creates `config.rc` from `config.rc.example`
   - Adds `whx` alias to `~/.bashrc` pointing to `run.sh`

2. **`run.sh`** - Main entry point script (aliased as `whx` command):
   - Loads configuration from `config.rc`
   - Validates prerequisites (ffmpeg, whisperx)
   - Performs 3-stage audio preprocessing with ffmpeg
   - Invokes whisperx with specific parameters
   - Runs speaker matching (if enabled) or converts JSON to TXT
   - Cleans up temporary files via trap

3. **`config.rc`** - User configuration (not in git):
   - `HF_TOKEN` - Hugging Face token for diarization and speaker recognition models
   - `WHX_LANGUAGE` - default language for transcription (e.g., "ru")
   - `WHX_ENABLE_SPEAKER_MATCHING` - enable/disable speaker recognition (default: "false")
   - `WHX_SPEAKER_THRESHOLD` - cosine similarity threshold for matching (default: "0.75")

4. **`speakers/learn_speaker.sh`** - Create speaker profiles for recognition:
   - Validates audio sample (10-60 seconds)
   - Converts to 16kHz mono WAV
   - Automatically copies audio to `./samples/` directory
   - Extracts speaker embedding using pyannote.audio
   - Saves profile to `./speakers/data/{speaker_id}.npy`
   - Updates metadata in `./speakers/data/speakers.json` with relative audio path
   - Wrapper: `speakers/learn` (no .sh extension)

5. **`scripts/extract_speaker_embedding.py`** - Python script for embedding extraction
   - Accepts `--original_audio` parameter for metadata audio path
6. **`scripts/match_speakers.py`** - Python script for speaker matching and JSON→TXT conversion
7. **`scripts/utils.py`** - Utility functions for profile management
   - `get_speakers_dir()` returns `./speakers/data` (local storage)
8. **`speakers/list_speakers.sh`** - List all registered speaker profiles
   - Wrapper: `speakers/list`
9. **`speakers/delete_speaker.sh`** - Delete a speaker profile
   - Wrapper: `speakers/delete`

### Audio Processing Pipeline

The `run.sh` script processes media through these stages:

1. **Audio extraction** (if video): Extract to `${STEM}_raw.wav` (48kHz stereo PCM)
2. **Resampling**: Convert to `${STEM}_16k_mono.wav` (16kHz mono PCM)
3. **Normalization**: Apply loudnorm filter to `${STEM}_16k_mono_norm.wav`
4. **Transcription**: Run whisperx on normalized audio (outputs JSON)
5. **Speaker matching** (if enabled):
   - Load speaker profiles from `./speakers/data/`
   - Extract embeddings for each SPEAKER_XX from audio segments
   - Match against known profiles using cosine similarity
   - Replace SPEAKER_XX labels with real names in JSON
   - Convert JSON to TXT format
6. **Cleanup**: Delete temporary WAV files, keep final `.txt` and `.json`

### WhisperX Parameters

The script calls whisperx with these hardcoded defaults:
- `--model large-v3` (WhisperX model)
- `--diarize` (speaker diarization enabled)
- `--highlight_words True` (word-level timestamps)
- `--output_format json` (JSON output for post-processing)
- `--language "${WHX_LANGUAGE:-ru}"` (from config, defaults to "ru")
- `--hf_token="${HF_TOKEN:-}"` (from config)
- `--verbose False --print_progress True` (minimal logging)

### Environment Variables for Logging Suppression

The script sets these to reduce noise:
```bash
HF_HUB_DISABLE_PROGRESS_BARS=1
TRANSFORMERS_VERBOSITY=error
TOKENIZERS_PARALLELISM=false
PYTHONWARNINGS=ignore
```

## Development Commands

### Installation
```bash
./install.sh           # Install whisperx in venv, create config, add alias
source ~/.bashrc       # Reload shell to activate 'whx' alias
```

### Configuration
```bash
# Edit config.rc to set HF_TOKEN and WHX_LANGUAGE
nano config.rc
```

### Running Transcription
```bash
whx /path/to/media.mp4              # Standard usage
./run.sh /path/to/media.mp4         # Direct script invocation
```

### Speaker Recognition
```bash
# Create speaker profiles (one-time setup)
speakers/learn sample_john.wav "John Doe"
speakers/learn sample_jane.mp3 "Jane Smith"

# List registered speakers
speakers/list

# Delete a speaker profile
speakers/delete john_doe

# Enable speaker matching in config.rc
nano config.rc  # Set WHX_ENABLE_SPEAKER_MATCHING="true"

# Run transcription with speaker recognition
whx interview.mp4  # Output will show "John Doe" instead of SPEAKER_00
```

### Testing Changes to run.sh
Since `whx` is aliased to the script location, changes to `run.sh` take effect immediately without reinstallation.

### Debugging
```bash
# Remove 'set -euo pipefail' temporarily to debug errors
# Check temporary files by commenting out cleanup() trap
# Add 'set -x' at top of run.sh for verbose execution trace
```

## Important Notes

- **Target platform:** Debian 12 with NVIDIA GPU (requires CUDA for WhisperX)
- **Mixed codebase:** Bash scripts for main workflow, Python scripts for speaker recognition
- **File extensions:** Handles video (mkv, mp4, mov, avi, etc.) and audio (wav, mp3, flac, etc.)
- **Cleanup:** All temporary WAV files are automatically deleted via EXIT trap
- **Output location:** Transcript `.txt` and `.json` are always written next to the input file
- **Installation quirk:** The alias points to the absolute path of `run.sh`, so the repo can be moved but requires re-running `install.sh`
- **Speaker profiles location:** `./speakers/data/` (local to repository, portable)
- **Audio samples location:** `./samples/` (automatically populated by `speakers/learn`)
- **HuggingFace requirements:** Must accept pyannote/embedding license and use valid HF_TOKEN for speaker recognition

## Modifying Transcription Parameters

To change WhisperX behavior, edit the `whisperx` invocation in `run.sh` (lines 112-121):
- Model: Change `--model large-v3` to other Whisper models
- Diarization: Remove `--diarize` to disable speaker identification
- Output format: Currently set to `json` (required for speaker matching). To disable speaker matching and use other formats, change to `srt`, `vtt`, etc. and remove the speaker matching block
- Language: Modify default in `--language "${WHX_LANGUAGE:-ru}"`

## Speaker Recognition Architecture

### Data Flow

1. **Profile Creation** (`speakers/learn_speaker.sh`):
   - Input: 10-60s audio sample (any location)
   - Process:
     - Copy audio to `./samples/` directory (if not already there)
     - ffmpeg conversion → pyannote.audio embedding extraction
   - Output:
     - `./speakers/data/{id}.npy` (512-dim vector)
     - `./samples/{audio_file}` (copy of original audio)
     - metadata JSON with relative path to audio

2. **Speaker Matching** (`match_speakers.py`):
   - Input: WhisperX JSON + normalized audio + speaker profiles
   - Process:
     - Extract segments for each SPEAKER_XX from JSON
     - Extract embeddings from audio using pyannote.audio
     - Compute cosine similarity with all profiles
     - Apply threshold (default 0.75) to determine matches
   - Output: Updated JSON with real names + TXT transcript

### Speaker Matching Algorithm

1. Load all speaker profiles from `./speakers/data/*.npy`
2. For each SPEAKER_XX in WhisperX output:
   - Extract all segments >2 seconds for that speaker
   - Process up to 10 longest segments (for performance)
   - Extract embedding for each segment using pyannote.audio
   - Average all segment embeddings into single vector
3. Compare speaker vector with each profile using cosine similarity
4. If best match score >= threshold: replace SPEAKER_XX with profile name
5. If no match: keep SPEAKER_XX label

### File Structure

```
whx/
├── speakers/
│   ├── data/
│   │   ├── john_doe.npy          # NumPy array (512-dim embedding)
│   │   ├── jane_smith.npy        # NumPy array (512-dim embedding)
│   │   └── speakers.json         # Metadata for all profiles
│   ├── learn_speaker.sh          # Main implementation
│   ├── delete_speaker.sh         # Main implementation
│   ├── list_speakers.sh          # Main implementation
│   ├── learn                     # Wrapper (no .sh)
│   ├── delete                    # Wrapper (no .sh)
│   └── list                      # Wrapper (no .sh)
└── samples/
    ├── sample_john.wav           # Audio sample for John
    └── sample_jane.mp3           # Audio sample for Jane
```

**speakers.json example:**
```json
{
  "john_doe": {
    "name": "John Doe",
    "created": "2024-01-30T...",
    "audio_file": "samples/sample_john.wav",
    "duration": 25.3,
    "embedding_dim": 512,
    "model": "pyannote/embedding"
  }
}
```

### Configuration Variables

- `WHX_ENABLE_SPEAKER_MATCHING`: "true"/"false" - enable/disable feature
- `WHX_SPEAKER_THRESHOLD`: 0.0-1.0 - minimum cosine similarity for match
  - 0.75 (default): balanced, works for most cases
  - 0.80-0.85: stricter, fewer false positives
  - 0.65-0.70: looser, more matches but higher risk of errors

### Fallback Behavior

Speaker matching gracefully degrades:
- No profiles → plain SPEAKER_XX labels
- No match found → keep SPEAKER_XX label
- Speaker matching disabled → convert JSON to TXT without matching
- pyannote.audio error → fallback to SPEAKER_XX labels
