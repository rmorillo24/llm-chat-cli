import requests
from .base_chat import BaseChatClient
from typing import Dict, List

class GeminiChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """Envía un mensaje a la API de Gemini y devuelve la respuesta."""
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key
        }
        payload = {
            'contents': [
                {'parts': [{'text': msg['content']}]}
                for msg in messages if msg['role'] in ['user', 'system']
            ],
            'generationConfig': {
                'temperature': temperature
            },
            'safetySettings': [
                {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
            ]
        }
        response = requests.post(f"{self.api_base}/models/{self.model_name}:generateContent",
                               headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']