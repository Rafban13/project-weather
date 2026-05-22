import os
from google.cloud import speech

class SpeechToTextClient:
    def __init__(self):
        self.client = speech.SpeechClient()

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to text using Google Speech-to-Text."""
        try:
            audio = speech.RecognitionAudio(content=audio_bytes)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
                sample_rate_hertz=16000,
                language_code="fr-FR",
                enable_automatic_punctuation=True,
            )
            response = self.client.recognize(config=config, audio=audio)
            if response.results:
                return response.results[0].alternatives[0].transcript
            return ""
        except Exception as e:
            raise Exception(f"Failed to transcribe audio: {e}")