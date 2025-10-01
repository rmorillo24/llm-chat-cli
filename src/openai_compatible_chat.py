# openai_compatible_chat.py
from typing import Dict, List
from .base_chat import BaseChatClient

class OpenAiCompatibleChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        data = self._send_request(f"{self.api_base}/v1/chat/completions", headers, payload)
        return self._parse_response(data)
