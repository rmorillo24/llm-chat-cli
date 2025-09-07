from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseChatClient(ABC):
    def __init__(self, config: Dict[str, Any], model_config: Dict[str, Any]):
        self.api_base = config['api_base']
        self.api_key = config.get('api_key', '')
        self.model_name = model_config['name']

    @abstractmethod
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        pass