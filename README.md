# whisper-ptt

Push-to-talk voice transcription that types at your cursor. Hold **Ctrl+Shift+Space** to record, release to transcribe and type — works in any app including Claude Code.

Built with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) running locally on CPU. No cloud, no API key.

## Features

- Global hotkey (Ctrl+Shift+Space) — push-to-talk, works system-wide
- Floating animated icon appears while recording
- Transcribed text typed at current cursor position
- Optimized for web dev, Python, data analysis, and local AI tooling vocabulary
- Fast: ~1s latency on CPU using Whisper `base` model with int8 quantization

## Requirements

- Python 3.11+
- [conda](https://docs.conda.io/) (or any venv)
- Windows (uses Win32 APIs for focus management)

## Setup

```bash
conda create -n whisper-cpu python=3.11
conda activate whisper-cpu
pip install faster-whisper sounddevice scipy keyboard pyperclip pyautogui
```

## Usage

```bash
conda activate whisper-cpu
python transcribe.py
```

On first run the Whisper `base` model (~150MB) is downloaded and cached. After that it loads in ~2s.

- **Hold** Ctrl+Shift+Space → floating icon appears, mic is recording
- **Release** → transcription types at your cursor
- **Ctrl+C** in the terminal to quit

## Configuration

At the top of `transcribe.py`:

| Constant | Default | Description |
|---|---|---|
| `SAMPLERATE` | `16000` | Mic sample rate (Hz) |
| `MIN_DURATION` | `0.2` | Minimum press duration (seconds) before transcribing |

Model and prompt are set in `_transcribe_and_deliver()`. Swap `"base"` for `"tiny"` (faster, less accurate) or `"small"` / `"medium"` (slower, more accurate).
