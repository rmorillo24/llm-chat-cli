# gemini_chat.py
from typing import Dict, List
from .base_chat import BaseChatClient

class GeminiChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key
        }
        payload = {
            'contents': [
                {'parts': [{'text': msg['content']}]}
                for msg in messages if msg['role'] in ['user', 'system']
            ],
            'generationConfig': {'temperature': temperature},
            'safetySettings': [
                {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
                {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
            ]
        }
        data = self._send_request(f"{self.api_base}/models/{self.model_name}:generateContent", headers, payload)
        try:
            return data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError) as parse_err:
            raise RuntimeError(
                f"Invalid response format from GeminiChat (model: {self.model_name}): {parse_err}"
            ) from parse_err
