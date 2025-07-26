"""
Audio Transcriber Module
Downloads audio from Infobip URLs and transcribes to English.
"""

from .transcriber import transcribe_from_infobip_url, transcribe_audio_file

__all__ = ['transcribe_from_infobip_url', 'transcribe_audio_file'] 