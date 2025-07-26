#!/usr/bin/env python3
"""
Test script for the audio_transcriber module.
"""

from audio_transcriber import transcribe_from_infobip_url, transcribe_audio_file

def test_infobip_url_transcription():
    """Test transcription from Infobip URL with automatic cleanup."""
    
    # Example Infobip media URL
    audio_url = "https://api.infobip.com/whatsapp/1/senders/96179374241/media/20288_11_733744599387627"
    
    try:
        print("🎤 Transcribing audio from Infobip URL...")
        print(f"🔗 URL: {audio_url}")
        print("⏳ Downloading, converting, and transcribing...")
        
        language, transcription = transcribe_from_infobip_url(audio_url)
        
        print(f"\n✅ Result: Language: {language} | Transcription: {transcription}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_local_file_transcription():
    """Test transcription from local file."""
    
    local_file = "downloaded_media/infobip_audio_20250719_145952.oga"
    
    try:
        print(f"\n🎤 Transcribing local audio file: {local_file}")
        
        language, transcription = transcribe_audio_file(local_file)
        
        print(f"✅ Result: Language: {language} | Transcription: {transcription}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("AUDIO TRANSCRIBER MODULE TEST")
    print("=" * 60)
    
    # Test 1: Transcribe from Infobip URL (downloads, transcribes, cleans up)
    test_infobip_url_transcription()
    
    # Test 2: Transcribe local file
    test_local_file_transcription()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60) 