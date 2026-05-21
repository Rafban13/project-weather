import os
from google.cloud import speech

class SpeechToTextClient:
    def __init__(self):
        self.client = speech.SpeechClient()
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
        )

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to text using Google Speech-to-Text."""
        try:
            audio = speech.RecognitionAudio(content=audio_bytes)
            response = self.client.recognize(
                config=self.config,
                audio=audio
            )
            if response.results:
                return response.results[0].alternatives[0].transcript
            return ""
        except Exception as e:
            raise Exception(f"Failed to transcribe audio: {e}")