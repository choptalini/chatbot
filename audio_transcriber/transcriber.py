#!/usr/bin/env python3
"""
Audio Transcriber Module
Downloads audio from Infobip URLs, transcribes to English, and cleans up temporary files.
"""

import os
import subprocess
import tempfile
import shutil
import requests
import mimetypes
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from typing import Tuple
from datetime import datetime

def download_infobip_audio(media_url: str, temp_dir: Path) -> Path:
    """
    Download audio file from Infobip URL to temporary directory.
    
    Args:
        media_url: Infobip media URL
        temp_dir: Temporary directory path
        
    Returns:
        Path to downloaded audio file
    """
    load_dotenv()
    
    api_key = os.getenv("INFOBIP_API_KEY")
    if not api_key:
        raise ValueError("INFOBIP_API_KEY not found in .env file")

    headers = {
        "Authorization": f"App {api_key}",
        "Accept": "application/octet-stream"
    }

    try:
        response = requests.get(media_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        # Determine file extension from Content-Type
        content_type = response.headers.get('content-type')
        extension = mimetypes.guess_extension(content_type) if content_type else '.audio'
        if not extension:
            if content_type and 'audio' in content_type:
                extension = f".{content_type.split('/')[-1]}"
            else:
                extension = ".bin"

        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"infobip_audio_{timestamp}{extension}"
        file_path = temp_dir / filename

        # Download file
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path

    except requests.exceptions.HTTPError as http_err:
        raise RuntimeError(f"HTTP error downloading audio: {http_err}")
    except requests.exceptions.RequestException as req_err:
        raise RuntimeError(f"Request error downloading audio: {req_err}")

def convert_to_mp3(input_path: Path, temp_dir: Path) -> Path:
    """
    Convert audio file to MP3 format using ffmpeg.
    
    Args:
        input_path: Path to input audio file
        temp_dir: Temporary directory for output
        
    Returns:
        Path to converted MP3 file
    """
    if input_path.suffix.lower() == '.mp3':
        return input_path
    
    mp3_path = temp_dir / f"{input_path.stem}.mp3"
    
    cmd = ['ffmpeg', '-i', str(input_path), '-acodec', 'mp3', '-ab', '192k', '-y', str(mp3_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
    
    return mp3_path

def transcribe_audio_file(audio_path: str) -> Tuple[str, str]:
    """
    Transcribe audio file to English and detect original language.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Tuple of (detected_language, english_transcription)
    """
    load_dotenv()
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file")
    
    client = OpenAI(api_key=api_key)
    
    with open(audio_path, "rb") as audio_file:
        # First detect language using transcription
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json"
        )
        detected_language = transcription.language
        
        # Then translate to English
        audio_file.seek(0)
        translation = client.audio.translations.create(
            model="whisper-1",
            file=audio_file,
            prompt="Translate this audio to English."
        )
        english_text = translation.text
    
    return detected_language, english_text

def transcribe_from_infobip_url(media_url: str) -> Tuple[str, str]:
    """
    Download audio from Infobip URL, transcribe to English, and clean up.
    
    Args:
        media_url: Infobip media URL
        
    Returns:
        Tuple of (detected_language, english_transcription)
    """
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="audio_transcriber_"))
    
    try:
        # Download audio
        audio_file = download_infobip_audio(media_url, temp_dir)
        
        # Convert to MP3 if needed
        mp3_file = convert_to_mp3(audio_file, temp_dir)
        
        # Transcribe
        language, transcription = transcribe_audio_file(str(mp3_file))
        
        return language, transcription
        
    finally:
        # Clean up temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir) 