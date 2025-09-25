from dataclasses import dataclass
import yaml
import re
from typing import Optional, List, Dict, Literal
from .xai_chat import XaiChat
from .gemini_chat import GeminiChat
from .base_chat import BaseChatClient
from .openai_chat import OpenAiChat
from .openai_compatible_chat import OpenAiCompatibleChat
from .config_manager import ConfigManager
from pathlib import Path
import logging
from .config_manager import ConfigManager
import os

RoleKind = Literal['system', 'embedded', 'fewshot']

@dataclass
class RoleConfig:
    name: str
    template: str = ""                  # raw role body
    kind: Optional[RoleKind] = None     # detect if None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    description: Optional[str] = None   # Added for role description

    def detect_role_kind(self, template: str) -> RoleKind:
        if re.search(r'###\s*INPUT:.*###\s*OUTPUT:', template, re.S):
            return 'fewshot'
        if '__INPUT__' in template or '{__INPUT__}' in template:
            return 'embedded'
        return 'system'

class LLMClient:
    def __init__(self, config_manager: ConfigManager, roles_path: str = None):
        try:
            self.logger = logging.getLogger("llmchat.llmclient")
        except:
            print("couldn't get logger")
        self.config_manager = config_manager 
        self.config = config_manager.get_config()
        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        self.active_role: Optional[RoleConfig] = None
        self.roles = self._load_roles(roles_path) if roles_path else {}
        self.load_model() # loads the default model
        self.history = []

    def _load_roles(self, roles_path: str) -> Dict[str, RoleConfig]:
        """Load roles from a YAML file."""
        try:
            roles_path = Path(roles_path)
            with roles_path.open('r') as f:
                roles_data = yaml.safe_load(f) or {'roles': []}
            return {
                role['name']: RoleConfig(
                    name=role['name'],
                    template=role.get('template', ''),
                    kind=role.get('kind'),
                    model=role.get('model'),
                    temperature=role.get('temperature'),
                    top_p=role.get('top_p'),
                    description=role.get('description')
                ) for role in roles_data.get('roles', [])
            }
        except FileNotFoundError:
            self.logger.warning(f"Roles file {roles_path} not found")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing roles YAML file: {e}")
            return {}

    def set_role(self, role: RoleConfig):
        role.kind = role.kind or role.detect_role_kind(role.template)
        self.active_role = role
        if role.model and role.model != self.current_model:
            self.load_model(role.model)

    def clear_role(self):
        self.active_role = None
        if self.current_model != self.default_model and self.default_model:
            self.load_model(self.default_model)

    def load_model(self, model: str = None) -> None:
        model = model or self.default_model
        self.logger.debug("load_model -> loading model: %s", model)
        if not model:
            raise ValueError("No model specified and default model not present")

        provider, model_name, *version = model.split(':') if ':' in model else (None, model)
        if version: model_name += ":" + version[0]
        self.logger.debug("load_model -> provider: %s, model_name: %s", provider, model_name)

        if not provider or not model_name:
            raise ValueError(f"Invalid format: {model}. Expecting 'provider:model'")
        if provider not in self.clients:
            raise ValueError(f"Provider {provider} not found in config file")

        client_config = self.clients[provider]
        if client_config["api_key"].startswith('$'):
            envvar = client_config["api_key"][1:]
            client_config["api_key"] = os.getenv(envvar, client_config["api_key"])
        model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
        self.logger.debug("client config loaded: %s", client_config)
        self.logger.debug("model config loaded: %s", model_config)
        if not model_config:
            raise ValueError(f"Model {model_name} for provider {provider}")

        if provider == 'grok':
            self.current_client = XaiChat(client_config, model_config)
        elif provider == 'gemini':
            self.current_client = GeminiChat(client_config, model_config)
        elif provider == 'openai':
            self.current_client = OpenAiChat(client_config, model_config)
        elif provider == 'openai-compatible':
            self.current_client = OpenAiCompatibleChat(client_config, model_config)
        else:
            raise ValueError(f"Provider type {provider} not supported")

        self.current_model = model

    def send_message(self, messages: List[Dict[str, str]], temperature: float = 1.0, top_p=None) -> str:
        if self.current_client is None:
            raise ValueError("No model loaded.")
        return self.current_client.send_message(messages, temperature)

    def list_models(self):
        models = []
        for provider in self.config["clients"]:
            for model in provider["models"]:
                models.append(provider["type"] + ":" + model['name'] )
        return models

    def get_config(self):
        return self.config

    def fill_embedded(self, template: str, user_input: str) -> str:
        return (template
                .replace('{__INPUT__}', user_input)
                .replace('__INPUT__', user_input))


    def neutralize_history(self) -> List[Dict[str, str]]:
        SCAFFOLD_MARK = re.compile(r'###\s*INPUT:|###\s*OUTPUT:', re.I)
        clean = []
        for m in self.history:
            if m.get('role') == 'system':
                continue
            if m.get('role') == 'user' and SCAFFOLD_MARK.search(m.get('content', '')):
                content = m.get('content', '')
                match = re.search(r'###\s*INPUT:\n(.*)\n###\s*OUTPUT:', content, re.S)
                if match:
                    clean.append({'role': 'user', 'content': match.group(1).strip()})
                continue
            clean.append(m)
        return clean


    def build_messages_for_role(self, 
                               user_input: str,
                               role: Optional[RoleConfig] = None) -> List[Dict[str, str]]:
        hist = self.neutralize_history()  # Always neutralize for consistency
        if role is None:
            return hist + [{'role': 'user', 'content': user_input}]  
        
        kind = role.kind or role.detect_role_kind(role.template)
        if kind == 'system':
            return [{'role': 'system', 'content': role.template}] + hist + [{'role': 'user', 'content': user_input}]
        else:  # embedded or fewshot
            return hist + [{'role': 'user', 'content': self.fill_embedded(role.template, user_input)}]


    def send_with_role(self,
                       user_input: str,
                       temperature: Optional[float] = None,
                       top_p: Optional[float] = None) -> str:
        if self.current_client is None:
            raise ValueError("No model loaded.")
        
        role = self.active_role
        messages = self.build_messages_for_role(user_input, role=role)  # Temp messages, don't set self.history
        
        eff_temperature = (role.temperature if role and role.temperature is not None
                           else temperature if temperature is not None
                           else 1.0)
        eff_top_p = (role.top_p if role and role.top_p is not None
                     else top_p)
 
        response = self.current_client.send_message(messages, temperature=eff_temperature)
        
        self.history.append({'role': 'user', 'content': user_input}) 
        self.history.append({'role': 'assistant', 'content': response})
        
        return response


    def get_current_model(self):
        return self.current_model


    def get_history(self) -> []:
        return self.history
