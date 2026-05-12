import os
from google.cloud import texttospeech

class TextToSpeechClient:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient()
        
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Casual-K"
        )
        
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

    def generate_speech(self, text: str) -> bytes:
        """Convert text to speech audio bytes."""
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            return response.audio_content
        except Exception as e:
            raise Exception(f"Failed to generate speech: {e}")