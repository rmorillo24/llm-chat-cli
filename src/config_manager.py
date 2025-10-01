import yaml
import requests
from pathlib import Path
from typing import Dict, Any
import subprocess
import logging

class ConfigManager:
    """Manages loading, updating, and saving configuration from a YAML file."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.logger = logging.getLogger("llmchat.config_manager")

    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from the YAML file."""
        try:
            with self.config_path.open('r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file {self.config_path} not found")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

    def get_config(self) -> Dict[str, Any]:
        """Return the current configuration."""
        return self.config

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update the in-memory configuration and save to file."""
        self.config = new_config
        self._save_config()

    def _save_config(self) -> None:
        """Save the current configuration to the YAML file."""
        try:
            with self.config_path.open('w') as f:
                print("SAVING CONFIGURATION TO FILE")
                yaml.safe_dump(self.config, f, sort_keys=False)
        except Exception as e:
            raise IOError(f"Error saving config to {self.config_path}: {e}")

    def update_ollama_models(self):
        try:
            # Step 1: Find all Ollama clients (type: openai-compatible)
            ollama_clients = [
                client for client in self.config.get('clients', [])
                if client.get('type') == 'ollama'
            ]
            if not ollama_clients:
                raise ValueError("No Ollama clients (type: ollamollamaa) found in configuration")

            # Step 2: If multiple Ollama clients, prompt user to select one
            if len(ollama_clients) > 1:
                choices = [client['name'] for client in ollama_clients]
                print(choices)
                selected_client_name = questionary.select(
                    "Select an Ollama client to update:",
                    choices=choices
                ).ask()
                if not selected_client_name:
                    self.logger.info("No client selected, aborting update")
                    return
                ollama_client = next(
                    (client for client in ollama_clients if client['name'] == selected_client_name),
                    None
                )
            else:
                ollama_client = ollama_clients[0]
                selected_client_name = ollama_client['name']

            if not ollama_client:
                raise ValueError(f"Selected Ollama client {selected_client_name} not found")

            # Step 3: Get model names from Ollama server via HTTP API
            api_base = ollama_client.get('api_base')
            if not api_base:
                raise ValueError(f"No api_base defined for Ollama client {selected_client_name}")
            response = requests.get(f"{api_base}/api/tags")
            response.raise_for_status()
            data = response.json()
            ollama_models = [model['name'] for model in data.get('models', []) if model.get('name')]
            self.logger.debug("Existing Ollama models for %s: %s", selected_client_name, ollama_models)

            # Step 4: Get current models from config for the selected client
            config_models = {model['name'] for model in ollama_client.get('models', [])}
            self.logger.debug("Ollama models in config for %s: %s", selected_client_name, config_models)

            # Step 5: Add new models from Ollama to config
            for model_name in ollama_models:
                if model_name not in config_models:
                    ollama_client['models'].append({
                        'name': model_name,
                        'max_input_tokens': 128000  # Default value from existing config
                    })
                    self.logger.debug("Added model %s to config for %s", model_name, selected_client_name)

            # Step 6: Remove models from config that are not in Ollama
            ollama_client['models'] = [
                model for model in ollama_client['models']
                if model['name'] in ollama_models
            ]
            self.logger.debug("Updated Ollama models in config for %s: %s", selected_client_name, [model['name'] for model in ollama_client['models']])

            # Step 7: Update the config file
            self.update_config(self.config)
            self.logger.info("Updated %s with current Ollama models for %s: %s", self.config_path, selected_client_name, [model['name'] for model in ollama_client['models']])

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching models from Ollama API for {selected_client_name}: {e}")
        except Exception as e:
            self.logger.error(f"Error updating configuration for {selected_client_name}: {e}")
