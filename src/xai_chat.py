# xai_chat.py
from typing import Dict, List
from .base_chat import BaseChatClient

class XaiChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': self.model_name,
            'messages': messages,
            'temperature': temperature
        }
        data = self._send_request(f"{self.api_base}/chat/completions", headers, payload)
        return self._parse_response(data)
