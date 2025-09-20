#!/usr/bin/env python3

import os
import yaml
import timeit
import subprocess
from pathlib import Path
from clients import BaseChatClient, XaiChat, GeminiChat, OpenAiCompatibleChat, OpenAiChat
from utils import ConfigManager
from typing import Dict, Any, List
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
import logging
import questionary

TIMING = True

logger = logging.getLogger('my_app')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

from dataclasses import dataclass
import re
from typing import Optional, List, Dict, Literal

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
        self.config_manager = config_manager 
        self.config = config_manager.get_config()
        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        self.active_role: Optional[RoleConfig] = None
        self.roles = self._load_roles(roles_path) if roles_path else {}
        self.load_model() # loads the default model

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
            logger.warning(f"Roles file {roles_path} not found")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing roles YAML file: {e}")
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
        logger.debug("load_model -> loading model: %s", model)
        if not model:
            raise ValueError("No model specified and default model not present")

        provider, model_name, *version = model.split(':') if ':' in model else (None, model)
        if version: model_name += ":" + version[0]
        logger.debug("load_model -> provider: %s, model_name: %s", provider, model_name)

        if not provider or not model_name:
            raise ValueError(f"Invalid format: {model}. Expecting 'provider:model'")
        if provider not in self.clients:
            raise ValueError(f"Provider {provider} not found in config file")

        client_config = self.clients[provider]
        if client_config["api_key"].startswith('$'):
            envvar = client_config["api_key"][1:]
            client_config["api_key"] = os.getenv(envvar, client_config["api_key"])
        model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
        logger.debug("client config loaded: %s", client_config)
        logger.debug("model config loaded: %s", model_config)
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

    def neutralize_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        SCAFFOLD_MARK = re.compile(r'###\s*INPUT:|###\s*OUTPUT:', re.I)
        clean = []
        for m in history:
            if m.get('role') == 'system':
                continue
            if m.get('role') == 'user' and SCAFFOLD_MARK.search(m.get('content', '')):
                continue
            clean.append(m)
        return clean

    def build_messages_for_role(self, 
                               user_input: str,
                               history: List[Dict[str, str]],
                               role: Optional[RoleConfig] = None) -> List[Dict[str, str]]:
        if role is None:
            return [*history, {'role': 'user', 'content': user_input}]
        kind = role.kind or role.detect_role_kind(role.template)
        hist = self.neutralize_history(history)

        if kind == 'system':
            return [
                {'role': 'system', 'content': role.template},
                *hist,
                {'role': 'user', 'content': user_input},
            ]

        if kind == 'embedded':
            return [
                *hist,
                {'role': 'user', 'content': self.fill_embedded(role.template, user_input)},
            ]

        if kind == 'fewshot':
            return [
                *hist,
                {'role': 'user', 'content': self.fill_embedded(role.template, user_input)},
            ]

    def send_with_role(self,
                       user_input: str,
                       history: List[Dict[str, str]] = None,
                       temperature: Optional[float] = None,
                       top_p: Optional[float] = None) -> str:
        if self.current_client is None:
            raise ValueError("No model loaded.")
        history = history or []

        role = self.active_role
        messages = self.build_messages_for_role(user_input, role=role, history=history)

        eff_temperature = (role.temperature if role and role.temperature is not None
                           else temperature if temperature is not None
                           else 1.0)
        eff_top_p = (role.top_p if role and role.top_p is not None
                     else top_p)

        return self.current_client.send_message(messages, temperature=eff_temperature)

class CommandHandler:
    def __init__(self, config_manager: ConfigManager, llm_client: 'LLMClient'):
        self.commands = {
            ':exit': self._exit,
            ':q': self._exit,
            ':help': self._help,
            ':clear': self._clear,
            ':models': self._models,
            ':updateollama': self._update_ollama_models,
            ':set': self._set,
            ':role': self._role,
            ':listroles': self._list_roles
        }
        self.args = []
        self.config_manager = config_manager
        self.llm_client = llm_client

    def _exit(self):
        print("Bye!")
        return False

    def _help(self):
        print("Available commands: ", *self.commands)
        return True

    def _clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        return True

    def _models(self):
        models = self.llm_client.list_models()
        selected_model = questionary.select(
            "Select a model:",
            choices=models
        ).ask()
        self.llm_client.load_model(selected_model)
        return True

    def _set(self):
        global TIMING
        if self.args and self.args[0] == "timing":
            TIMING = True
        elif self.args and self.args[0] == "notiming":
            TIMING = False
        return True

    def _update_ollama_models(self):
        self.config_manager.update_ollama_models()
        return True

    def _list_roles(self):
        if not self.llm_client.roles:
            print("No roles available.")
            return True
        choices = [f"{name}: {role.description or 'No description'}" for name, role in self.llm_client.roles.items()]
        selected_role = questionary.select(
            "Select a role:",
            choices=choices
        ).ask()
        if selected_role:
            role_name = selected_role.split(':')[0]
            self.llm_client.set_role(self.llm_client.roles[role_name])
            print(f"Role set to {role_name}")
        return True

    def _role(self):
        if not self.args:
            print("Add a role name to the command or use :listroles to see available roles")
            return True
        selected_role = self.args[0]
        if selected_role == 'none':
            self.llm_client.clear_role()
            print("Role cleared")
            return True
        if selected_role not in self.llm_client.roles:
            print(f"Role {selected_role} not found. Use :listroles to see available roles")
            return True
        self.llm_client.set_role(self.llm_client.roles[selected_role])
        print(f"Role set to {selected_role}")
        return True

    def _unknown_command(self):
        print("Unknown command. Try one of these:")
        print(*self.commands)
        return True

    def handle_input(self, user_input):
        command, *self.args = user_input.strip().split(maxsplit=1)
        self.args = self.args[0].split() if self.args else []
        if command.startswith(":"):
            action = self.commands.get(command, self._unknown_command)
            return action()
        else:
            try:
                message = self.llm_client.build_messages_for_role(user_input, history=messages)
                start = timeit.default_timer()
                response = self.llm_client.send_with_role(user_input, history=messages)
                end = timeit.default_timer()
                messages.append({"role": "assistant", "content": response})
                
                if TIMING:
                    response += f"\n\n{end - start:.2f} sec."
                
                md = Markdown(response)
                with console.pager(styles=True, links=True):
                    console.print(md)
                
            except Exception as e:
                logger.error(f"Error: {e}")
            return True

if __name__ == "__main__":
    os.environ.setdefault("PAGER", "less -RFX")
    
    try:
        config_manager = ConfigManager(Path.home() / ".config" / "llm-chat-cli" / "configs.yaml")
        console = Console(record=True)
        llm_client = LLMClient(config_manager, roles_path=Path.home() / ".config" / "llm-chat-cli" / "roles.yaml")
        command_handler = CommandHandler(config_manager, llm_client)
        code_role = RoleConfig(
            name='%code%',
            template="### INPUT:\n{__INPUT__}\n### OUTPUT:",
            temperature=0.2,
            top_p=0.9
        )
        llm_client.set_role(code_role)
        logger.debug("config manager set")
        llm_client.load_model()
        logger.debug("loaded default model")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        exit(1)
        
    messages = [
        {'role': 'system', 'content': 'You are my assistant. I want short and concise answers without decoration or polite, unnecessary words.'}
    ]

    st = True
    while st:
        prompt = Text("\n> ", style="white on @1f2430 bold")
        user_input = console.input(prompt)
        console.print("\n")
        st = command_handler.handle_input(user_input)
        console.print("\n")
