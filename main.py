#!/usr/bin/env python3

import os
import argparse
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
TIMING =False 

class LLMClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager 
        self.config = config_manager.get_config()

        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        self.load_model() #loads the default model


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
            ':set': self._set
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
        TIMING = (TIMING and not (self.args[0] == "notiming")
                 or self.args[0] == "timing")
        return True
    '''
    if self.args[0] == "timing":
                TIMING = True
                print("Printing output timing")
        if self.args[0] == "notiming":
                TIMING = False
                print("Not printing output timing")
        return True
    '''

    def _update_ollama_models(self):
        self.config_manager.update_ollama_models()
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
            
            if TIMING:
                 response += f"\n\n{end - start:.2f} sec."

            md = Markdown(response)
            with console.pager(styles=True, links=True):
                console.print(md)

        except Exception as e:
            print(f"Error con {model}: {e}")
        return True  




if __name__ == "__main__":
    os.environ.setdefault("PAGER", "less -RFX")

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', nargs=argparse.REMAINDER,
                        help='Ask the LLM only this one question')
    args = parser.parse_args()
    
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
    
    if args.c:
        user_input=' '.join(args.c)
        command_handler.handle_input(user_input)
    else:
        st = True
        while st:
            prompt = Text("\n> ", style="white on @1f2430 bold")
            user_input = console.input(prompt)
            st = command_handler.handle_input(user_input)
            # console.print("\n")
            

