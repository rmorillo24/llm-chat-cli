import requests
from .base_chat import BaseChatClient
from typing import Dict, List

class OpenAiChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """Envía un mensaje a la API de OpenAI y devuelve la respuesta."""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature
        }
        response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']