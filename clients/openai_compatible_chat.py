import requests
from .base_chat import BaseChatClient
from typing import Dict, List

class OpenAiCompatibleChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        """Envía un mensaje a una API compatible con OpenAI (e.g., Ollama) y devuelve la respuesta."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # Incluir la clave API solo si está presente
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=300,  # 🔹 always set a timeout
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            raise RuntimeError(
                f"HTTP error from chat server: {http_err.response.status_code} - {http_err.response.text}"
            ) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError("Failed to connect to the chat server.") from None
        except requests.exceptions.Timeout as timeout_err:
            raise RuntimeError("Request to chat server timed out.") from timeout_err
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"Unexpected error during request: {req_err}") from req_err

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as parse_err:
            raise RuntimeError(f"Invalid response format: {parse_err}") from parse_err

