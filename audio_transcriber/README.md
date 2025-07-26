# Audio Transcriber Module

A simple Python module for downloading audio from Infobip URLs and transcribing them to English with language detection.

## Features

- 🔗 **Download from Infobip URLs**: Automatically downloads audio files from Infobip media URLs
- 🎯 **Language Detection**: Detects the original language of the audio
- 🌍 **English Translation**: Translates audio to English using OpenAI's Whisper
- 🔄 **Format Conversion**: Automatically converts audio files to MP3 using ffmpeg
- 🧹 **Automatic Cleanup**: Creates temporary files and cleans them up automatically
- 📦 **Simple API**: Just two functions for all functionality

## Installation

Ensure you have the required dependencies:
```bash
pip install openai python-dotenv requests
```

Also ensure ffmpeg is installed on your system.

## Usage

### Import the module
```python
from audio_transcriber import transcribe_from_infobip_url, transcribe_audio_file
```

### Transcribe from Infobip URL (recommended)
```python
# Downloads, transcribes, and cleans up automatically
language, transcription = transcribe_from_infobip_url("https://api.infobip.com/...")
print(f"Language: {language} | Transcription: {transcription}")
```

### Transcribe local file
```python
# For existing audio files
language, transcription = transcribe_audio_file("path/to/audio.oga")
print(f"Language: {language} | Transcription: {transcription}")
```

## Environment Variables

Make sure your `.env` file contains:
```
OPENAI_API_KEY=your_openai_api_key
INFOBIP_API_KEY=your_infobip_api_key
```

## Return Format

Both functions return a tuple: `(detected_language, english_transcription)`
- `detected_language`: Language code (e.g., "arabic", "english", "spanish")
- `english_transcription`: The transcribed and translated text in English

## Example Output
```
Language: arabic | Transcription: Hi, good morning. I have a question. I want to ask you, what things do you have that I can buy from you?
``` 