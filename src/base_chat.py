# base_chat.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import requests

class BaseChatClient(ABC):
    def __init__(self, config: Dict[str, Any], model_config: Dict[str, Any]):
        self.api_base = config['api_base']
        self.api_key = config.get('api_key', '')
        self.model_name = model_config['name']
        self.timeout = 300  # Default timeout in seconds

    def _send_request(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an HTTP POST request and handle common exceptions."""
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            raise RuntimeError(
                f"HTTP error from {self.__class__.__name__} (model: {self.model_name}): "
                f"{http_err.response.status_code} - {http_err.response.text}"
            ) from http_err
        except requests.exceptions.ConnectionError as conn_err:
            raise RuntimeError(
                f"Failed to connect to {self.__class__.__name__} server: {self.api_base}"
            ) from conn_err
        except requests.exceptions.Timeout:
            raise RuntimeError(
                f"Request to {self.__class__.__name__} server timed out after {self.timeout}s"
            ) from None
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(
                f"Unexpected error during {self.__class__.__name__} request: {req_err}"
            ) from req_err

    def _parse_response(self, data: Dict[str, Any]) -> str:
        """Parse JSON response and handle common parsing errors."""
        try:
            # Subclasses must override this if the response structure differs
            return data['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError) as parse_err:
            raise RuntimeError(
                f"Invalid response format from {self.__class__.__name__} (model: {self.model_name}): {parse_err}"
            ) from parse_err

    @abstractmethod
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        pass
