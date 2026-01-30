# WhisperX Transcription Helper

This repository provides a convenient wrapper script around WhisperX for fast transcription of audio/video files with word-level timestamps and optional speaker diarization.  

The helper script prepares input media (audio extraction, resampling, and light loudness normalization) before invoking WhisperX.

Upstream WhisperX project: [`m-bain/whisperX`](https://github.com/m-bain/whisperX).

See [RATIONALE.md](RATIONALE.md) for the background and motivation behind this project.

## Features

- Preprocess media with `ffmpeg`:
  - extract audio from video if needed
  - resample to 16 kHz mono PCM
  - apply light loudness normalization
- Call WhisperX CLI with sensible defaults
- **Speaker Recognition**: Automatically match speaker labels (SPEAKER_00, SPEAKER_01) with known speaker profiles
- Save the final transcript as a `.txt` file next to the input
- Clean up temporary files automatically
- Simple configuration via `config.rc`
- Installed as `whx` command (alias added to your `~/.bashrc`)

## Prerequisites

- Debian 12 (bookworm) or compatible Linux
- NVIDIA GPU with recent drivers
- `ffmpeg`
- Python 3.10+

## Installation

Clone the repository and run the installer:

```bash
git clone https://github.com/arthur-cpp/whx
cd whx
./install.sh
````

The installer will:

* create a Python virtual environment in `./venv`
* install WhisperX and pyannote.audio into it
* copy `config.rc.example` to `config.rc` (for user customization)
* add an alias `whx` to your `~/.bashrc`

Reload your shell or run:

```bash
source ~/.bashrc
```

Now the `whx` command is available everywhere.

## Configuration

All user-specific settings live in `config.rc`. An example file `config.rc.example` is provided:

```bash
export HF_TOKEN="hf_xxx"
export WHX_LANGUAGE="ru"

# Speaker Recognition Settings
export WHX_ENABLE_SPEAKER_MATCHING="false"
export WHX_SPEAKER_THRESHOLD="0.75"
```

* `HF_TOKEN`: your Hugging Face access token (required for diarization and speaker recognition models).
* `WHX_LANGUAGE`: default language passed to WhisperX.
* `WHX_ENABLE_SPEAKER_MATCHING`: enable/disable automatic speaker name matching (default: `false`).
* `WHX_SPEAKER_THRESHOLD`: cosine similarity threshold for speaker matching (default: `0.75`).

Edit `config.rc` to set your values.

## Usage

Basic usage processes a single media file. The output `.txt` transcript will be written next to the input file using the same base name.

```bash
whx /path/to/media.(wav|mp3|flac|mkv|mp4|avi|...)
```

Steps performed:

1. Validate prerequisites (`ffmpeg`, `whisperx`)
2. Extract audio if the input is a video
3. Resample to 16 kHz mono PCM
4. Normalize loudness
5. Invoke `whisperx` with defaults:

   * `--model large-v3`
   * `--language $WHX_LANGUAGE` (from `config.rc`)
   * `--diarize`
   * `--highlight_words True`
   * `--output_format json`
   * output directory = same as input
6. Speaker matching (if enabled) or convert JSON to TXT format
7. Save final transcript next to the input

### Examples

* Transcribe a video:

  ```bash
  whx ~/videos/lecture.mp4
  # -> produces ~/videos/lecture.txt
  ```

* Transcribe an audio file:

  ```bash
  whx ~/audio/interview.wav
  # -> produces ~/audio/interview.txt
  ```

## Speaker Recognition

WhisperX provides speaker diarization (labeling segments as SPEAKER_00, SPEAKER_01, etc.), but doesn't identify who those speakers are. This project adds **automatic speaker recognition** to match speaker labels with real names.

### How It Works

1. **Create speaker profiles** from audio samples (one-time setup)
2. **Enable speaker matching** in config
3. **Run transcription** as usual - speaker names are automatically applied

### Creating Speaker Profiles

Record or extract 10-60 seconds of clear speech from each person you want to recognize. Then create their profile:

```bash
speakers/learn sample_john.wav "John Doe"
speakers/learn sample_jane.mp3 "Jane Smith"
```

This creates:
- `speakers/data/john_doe.npy` - speaker embedding vector
- `speakers/data/jane_smith.npy` - speaker embedding vector
- `speakers/data/speakers.json` - metadata
- `samples/sample_john.wav` - copy of audio sample (for portability)
- `samples/sample_jane.mp3` - copy of audio sample (for portability)

**Requirements for audio samples:**
- Duration: 10-60 seconds of continuous speech
- Quality: Clear voice, minimal background noise
- Content: Natural speech (not singing or whispered)

### Enabling Speaker Matching

Edit `config.rc`:

```bash
export WHX_ENABLE_SPEAKER_MATCHING="true"
export WHX_SPEAKER_THRESHOLD="0.75"  # adjust if needed (0.0-1.0)
```

Higher threshold = more strict matching (fewer false positives, more missed matches).

### Using Speaker Recognition

Once profiles are created and matching is enabled, just run transcription normally:

```bash
whx interview.mp4
```

The output will show real names instead of SPEAKER_XX:

```
[00:01.23] John Doe: Hello everyone.
[00:05.67] Jane Smith: Hi John, how are you?
[00:08.45] SPEAKER_02: Good morning.
```

**Note:** Unmatched speakers remain as SPEAKER_XX (either no profile exists, or similarity is below threshold).

### Managing Speaker Profiles

List all registered speakers:

```bash
speakers/list
```

Delete a speaker profile:

```bash
speakers/delete john_doe
```

### Speaker Recognition Requirements

To use speaker recognition, you must:

1. Visit https://huggingface.co/pyannote/embedding
2. Accept the user agreement
3. Use a HuggingFace token with read access in `config.rc`

The `pyannote.audio` library is installed automatically by `./install.sh`.

## Troubleshooting

* **`whisperx not found`**: make sure you ran `./install.sh` and activated the alias (`source ~/.bashrc`).
* **`ffmpeg not found`**: install via apt (`sudo apt-get install ffmpeg`).
* **Diarization auth errors**: check that `HF_TOKEN` in `config.rc` is valid.

If you encounter errors mentioning `libcudnn*` (e.g. `libcudnn_ops_infer.so.8: cannot open shared object file`):

- On **Debian 12 with NVIDIA drivers**, install the `nvidia-cudnn` package:

  ```bash
  sudo apt update
  sudo apt install -y nvidia-cudnn
  ```

- Otherwise, refer to the official WhisperX docs, section [Common Issues & Troubleshooting](https://github.com/m-bain/whisperX#common-issues--troubleshooting-).


## Credits and License

This project is licensed under the BSD 2-Clause License — see the [LICENSE](LICENSE) file for details.

- [WhisperX](https://github.com/m-bain/whisperX) by Max Bain et al., licensed under BSD-2-Clause.
