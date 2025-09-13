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

logging.basicConfig(level=logging.ERROR)
# logging.debug("Variable x = %s", x)
TIMING = True

class LLMClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager 
        self.config = config_manager.get_config()

        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        self.active_role: Optional[RoleConfig] = None
        self.load_model() #loads the default model

    def set_role(self, role: RoleConfig):
        role.kind = role.kind or detect_role_kind(role.template)
        self.active_role = role

        if role.model and role.model != self.current_model:
            self.load_model(role.model)

    def clear_role(self):
        self.active_role = None
        if self.current_model != self.default_model and self.default_model:
            self.load_model(self.default_model)


    def load_model(self, model: str = None) -> None:
        model = model or self.default_model
        logging.debug("load_model -> loading model: %s", model)
        if not model:
            raise ValueError("Model not specified and default model not present")

        provider, model_name, *version = model.split(':') if ':' in model else (None, model)
        if version: model_name += ":" + version[0]
        logging.debug("load_model -> provider: %s, model_name: %s", provider, model_name)

        if not provider or not model_name:
            raise ValueError(f"Invalid format: {model}. Expecting 'provider:model'")
        if provider not in self.clients:
            raise ValueError(f"Provider {provider} not found in config file")

        client_config = self.clients[provider]
        if client_config["api_key"].startswith('$'):
            envvar = client_config["api_key"][1:]
            client_config["api_key"] = os.getenv(envvar, client_config["api_key"])
        model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
        logging.debug("client config loaded: %s", client_config)
        logging.debug("model config loaded: %s", model_config)
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


    def send_message(self, messages: List[Dict[str, str]], temperature: float = 1.0) -> str:
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

    
    def fill_embedded(template: str, user_input: str) -> str:
        return (template
                .replace('{__INPUT__}', user_input)
                .replace('__INPUT__', user_input))

    
    def build_messages_for_role(role: Optional[RoleConfig],
                                user_input: str,
                                history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if role is None:
            # No role → just pass through
            return [*history, {'role': 'user', 'content': user_input}]

        kind = role.kind or detect_role_kind(role.template)
        hist = neutralize_history(history)

        if kind == 'system':
            return [
                {'role': 'system', 'content': role.template},
                *hist,
                {'role': 'user', 'content': user_input},
            ]

        if kind == 'embedded':
            return [
                *hist,
                {'role': 'user', 'content': fill_embedded(role.template, user_input)},
            ]

        # fewshot
        # If your template uses {__INPUT__} inside the block, replace it;
        # otherwise append INPUT/OUTPUT wrappers as-is.
        filled = fill_embedded(role.template, user_input)
        return [
            *hist,  # optional: prepend a brief neutral context message instead
            {'role': 'user', 'content': filled},
        ]



from dataclasses import dataclass
import re
from typing import Optional, List, Dict, Literal

RoleKind = Literal['system', 'embedded', 'fewshot']

@dataclass
class RoleConfig:
    name: str
    template: str                   # raw role body
    kind: Optional[RoleKind] = None # detect if None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    use_tools: Optional[bool] = None

    def detect_role_kind(template: str) -> RoleKind:
        if re.search(r'###\s*INPUT:.*###\s*OUTPUT:', template, re.S):
            return 'fewshot'
        if '__INPUT__' in template or '{__INPUT__}' in template:
            return 'embedded'
        return 'system'

           
class CommandHandler:
    def __init__(self, config_manager: ConfigManager):
        # Initialize the dispatch table with reserved words and their actions
        self.commands = {
            ':exit': self._exit,
            ':q': self._exit,
            ':help': self._help,
            ':clear': self._clear,
            ':models': self._models,
            ':updateollama': self._update_ollama_models,
            ':set': self._set,
            ':role': self._role
        }
        self.args = []
        self.config_manager = config_manager

    def _exit(self):
        print("Bye!")
        return False  # Signal to break the loop

    def _help(self):
        print("Available commands: ", *self.commands)
        return True  # Continue the loop

    def _clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal (Windows or Unix)
        return True  # Continue the loop

    def _models(self):
        models = llm_client.list_models()
        selected_model = questionary.select(
            "Select a model:",
            choices = models
        ).ask()
        llm_client.load_model(selected_model)
        return True

    def _set(self):
        global TIMING
        if self.args[0] == "timing":
                TIMING = True
        if self.args[0] == "notiming":
                TIMING = False
        return True

    def _update_ollama_models(self):
        self.config_manager.update_ollama_models()
        return True

    def handle_input(self, user_input):
        command, *self.args = user_input.lower().strip().split() 
        if command.startswith(":"):
            action = self.commands.get(command, self._unknown_command)  
            return action()  
        else:
            try:
                # messages.append({"role": "user", "content": user_input})
                message = llmclient.build_message_for_roles(user_input = user_input)
                start = timeit.default_timer()
                # response = llm_client.send_message(messages)
                print("MESSAGE")
                print(message) 
                sys.exit(0)
                end = timeit.default_timer()
                #messages.append({"role": "assistant", "content": response})
                
                if TIMING:
                    response += f"\n\n{end - start:.2f} sec."
                
                md = Markdown(response)
                with console.pager(styles=True, links=True):
                    console.print(md)
                
            except Exception as e:
                logging.error(f"Error con: {e}")


    def role(self):
        if not self.args[0]:
            print("Add a role name to the command")
        else:
            selected_role = self.args[0]
            # look for selected role template and load
            # message_content = <input>user_input<ouput>
            # tell llm client to change the role. Pass 
        return True

    def _unknown_command(self):
        print("Unkown command. Try one of these:")
        print(*self_commands)



if __name__ == "__main__":
    os.environ.setdefault("PAGER", "less -RFX")
    
    try:
        config_manager= ConfigManager(Path.home() / ".config" / "llm-chat-cli" / "configs.yaml")
        console = Console(force_terminal = True)
        command_handler = CommandHandler(config_manager)
        llm_client = LLMClient(config_manager)
        llm_client.load_model()  # Load default model for faster start
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
        

