import yaml
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, List

# Configuración YAML (igual que antes, pero simplificada)
CONFIG_YAML = """
model: openai:gpt-4o
clients:
  - type: openai
    api_base: https://api.openai.com/v1
    api_key: sk-xxx
    models:
      - name: gpt-4o
        max_input_tokens: 128000
  - type: grok
    api_base: https://api.grok.x.ai/v1
    api_key: xxx
    models:
      - name: grok-beta
        max_input_tokens: 128000
  - type: gemini
    api_base: https://generativelanguage.googleapis.com/v1beta
    api_key: xxx
    models:
      - name: gemini-1.5-pro
        max_input_tokens: 1000000
    patch:
      chat_completions:
        '.*':
          body:
            safetySettings:
              - category: HARM_CATEGORY_HARASSMENT
                threshold: BLOCK_NONE
  - type: openai-compatible
    name: ollama
    api_base: http://localhost:11434/v1
    api_key: xxx
    models:
      - name: llama3.2
        max_input_tokens: 128000
"""

# Clase base abstracta
class BaseChatClient(ABC):
    def __init__(self, config: Dict[str, Any], model_config: Dict[str, Any]):
        self.api_base = config['api_base']
        self.api_key = config.get('api_key', '')
        self.model_name = model_config['name']
    
    @abstractmethod
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        pass

# Cliente para OpenAI
class OpenAiChat(BaseChatClient):
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
        response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

# Cliente para xAI/Grok (compatible con OpenAI)
class XaiChat(OpenAiChat):
    pass  # Reutiliza la lógica de OpenAI, ya que es compatible

# Cliente para Ollama (compatible con OpenAI)
class OllamaChat(OpenAiChat):
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
        response = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

# Cliente para Gemini
class GeminiChat(BaseChatClient):
    def send_message(self, messages: List[Dict[str, str]], temperature: float) -> str:
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': self.api_key  # Gemini usa un header diferente
        }
        payload = {
            'contents': [
                {'parts': [{'text': msg['content']}]}
                for msg in messages if msg['role'] in ['user', 'system']  # Simplificado
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

# Factory para crear clientes
class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.clients = {client['type']: client for client in config['clients']}
        self.default_model = config.get('model', '')

    def get_client(self, model: str) -> BaseChatClient:
        provider, model_name = model.split(':') if ':' in model else (None, model)
        if provider not in self.clients:
            raise ValueError(f"Proveedor {provider} no encontrado")

        client_config = self.clients[provider]
        model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
        if not model_config:
            raise ValueError(f"Modelo {model_name} no encontrado")

        if provider == 'openai':
            return OpenAiChat(client_config, model_config)
        elif provider == 'grok':
            return XaiChat(client_config, model_config)
        elif provider == 'gemini':
            return GeminiChat(client_config, model_config)
        elif provider == 'openai-compatible':
            return OllamaChat(client_config, model_config)
        raise ValueError(f"Tipo de proveedor {provider} no soportado")

def main():
    config = yaml.safe_load(CONFIG_YAML)
    client = LLMClient(config)
    messages = [
        {'role': 'system', 'content': 'Eres un asistente útil.'},
        {'role': 'user', 'content': 'Hola, ¿qué es Python?'}
    ]
    models = ['openai:gpt-4o', 'grok:grok-beta', 'gemini:gemini-1.5-pro', 'openai-compatible:llama3.2']

    for model in models:
        try:
            print(f"\nLlamando a {model}...")
            chat_client = client.get_client(model)
            response = chat_client.send_message(messages, temperature=1.0)
            print(f"Respuesta de {model}: {response[:100]}...")
        except Exception as e:
            print(f"Error con {model}: {e}")

if __name__ == '__main__':
    main()
