import requests
from .base_chat import BaseChatClient
from typing import Dict, List

class OpenAiCompatibleChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """Envía un mensaje a una API compatible con OpenAI (e.g., Ollama) y devuelve la respuesta."""
        headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:  # Incluir la clave API solo si está presente
            headers['Authorization'] = f'Bearer {self.api_key}'
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature
        }
        response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']