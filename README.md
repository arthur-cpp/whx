# WhisperX Transcription Helper

This repository provides a convenient wrapper script around WhisperX for fast transcription of audio/video files with word-level timestamps and optional speaker diarization.  

The helper script prepares input media (audio extraction, resampling, and light loudness normalization) before invoking WhisperX.

Upstream WhisperX project: [`m-bain/whisperX`](https://github.com/m-bain/whisperX)

## Features

- Preprocess media with `ffmpeg`:
  - extract audio from video if needed
  - resample to 16 kHz mono PCM
  - apply light loudness normalization
- Call WhisperX CLI with sensible defaults
- Save the final transcript as a `.txt` file next to the input
- Clean up temporary files automatically
- Simple configuration via `config.rc`
- Installed as `whx` command (alias added to your `~/.bashrc`)

## Prerequisites

- Debian 12 (bookworm) or compatible Linux
- NVIDIA GPU with recent drivers (CUDA runtime from PyTorch wheels is used; no manual cuDNN installation needed)
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
* install WhisperX into it
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
```

* `HF_TOKEN`: your Hugging Face access token (required for diarization models).
* `WHX_LANGUAGE`: default language passed to WhisperX.

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
   * `--output_format txt`
   * output directory = same as input
6. Move the produced `.txt` next to the input

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
