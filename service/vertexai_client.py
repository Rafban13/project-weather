import os
import vertexai
from vertexai.generative_models import GenerativeModel

try:
    import config
    PROJECT_ID = config.PROJECT_ID
    PROJECT_LOCATION = config.PROJECT_LOCATION
except ImportError:
    PROJECT_ID = os.getenv('PROJECT_ID')
    PROJECT_LOCATION = os.getenv('PROJECT_LOCATION')

class VertexAIClient:
    def __init__(self):
        vertexai.init(project=PROJECT_ID, location="us-central1")

    def get_weather_description(self, weather_data: str, system_instruction: str) -> str:
        """Generate a natural language description of the weather using Gemini."""
        try:
            model = GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_instruction
            )
            chat = model.start_chat()
            response = chat.send_message(weather_data)
            return response.text
        except Exception as e:
            raise Exception(f"Failed to generate weather description: {e}")