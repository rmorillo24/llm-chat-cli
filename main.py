#!/usr/bin/env python3

import os
import yaml
import timeit
from pathlib import Path
from clients import BaseChatClient, XaiChat, GeminiChat, OpenAiCompatibleChat, OpenAiChat
from typing import Dict, Any, List
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
import logging
import questionary

logging.basicConfig(level=logging.INFO)
# logging.debug("Variable x = %s", x)
TIMING = True

class LLMClient:
    def __init__(self, config_path: str):
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                logging.debug("Loaded config: %s", self.config)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing the ysaml file: {e}")
        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        self.load_model() #loads the default model


    def load_model(self, model: str = None) -> None:
        model = model or self.default_model
        logging.debug("load_model -> loading model: %s", model)
        if not model:
            raise ValueError("Model not specified abd degault model not present")

        provider, model_name = model.split(':') if ':' in model else (None, model)
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


class CommandHandler:
    def __init__(self):
        # Initialize the dispatch table with reserved words and their actions
        self.commands = {
            '.exit': self._exit,
            '.help': self._help,
            '.clear': self._clear,
            '.models': self._models,
            '.set': self._set
        }
        self.args = []

    def _exit(self):
        print("Bye!")
        return False  # Signal to break the loop

    def _help(self):
        print("Available commands: .exit, .help, .clear, .models")
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
        print("setting", self.args)
        if self.args[0] == "timing":
                TIMING = True
        return True

    def handle_input(self, user_input):
        command, *self.args = user_input.lower().strip().split() 
        action = self.commands.get(command, self._unknown_command)  # Get action or default to unknown
        return action()  # Execute the action and return its result

    def _unknown_command(self):
        try:
            messages.append({"role": "user", "content": user_input})
            start = timeit.default_timer()
            response = llm_client.send_message(messages)
            end = timeit.default_timer()
            messages.append({"role": "assistant", "content": response})
            
            md = Markdown(response)
            with console.pager(styles=True, links=True):
                console.print(md)
                if TIMING: print(f"\n{end - start:.2f} sec.")

        except Exception as e:
            print(f"Error con {model}: {e}")
        return True  




if __name__ == "__main__":
    config_path = Path.home() / Path(".config/llm-chat-cli/configs.yaml")
    os.environ.setdefault("PAGER", "less -RFX")
    console = Console(force_terminal=True)
    command_handler = CommandHandler()
    
    try:
        llm_client = LLMClient(config_path)
        # command_handler.handle_input(".models")
        llm_client.load_model()  # Carga el modelo por defecto
    except Exception as e:
        print(f"Error al cargar la configuración: {e}")
        exit(1)
        
    messages = [
        {'role': 'system', 'content': 'You are my assistant. I want short and concise answers without decoration or polite, unnecessary words.'}
    ]

    st = True
    while st:
        prompt = Text("\n\n> ", style="white on @1f2430 bold")
        user_input = console.input(prompt)
        st = command_handler.handle_input(user_input)
        

