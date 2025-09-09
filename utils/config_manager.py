import yaml
from pathlib import Path
from typing import Dict, Any
import subprocess
import logging

class ConfigManager:
    """Manages loading, updating, and saving configuration from a YAML file."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()

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
                yaml.safe_dump(self.config, f, sort_keys=False)
        except Exception as e:
            raise IOError(f"Error saving config to {self.config_path}: {e}")

    def update_ollama_models(self):
        try:
            # Step 1: Get model names from Ollama server
            result = subprocess.run(
                ['docker', 'exec', '-it', 'ollama', 'ollama', 'list'],
                capture_output=True,
                text=True,
                check=True
            )
            # Extract model names from the first column, skipping header
            ollama_models = [
                line.split()[0] for line in result.stdout.strip().split('\n')[1:]
                if line.strip()
            ]
            logging.debug("existing ollama models: %s", ollama_models)

            # Step 2: Get current ollama models from config
            ollama_client = next(
                (client for client in self.config.get('clients', []) if client.get('name') == 'ollama'),
                None
            )
            logging.debug("Ollama_client: %s", ollama_client)
            if not ollama_client:
                raise ValueError("No ollama client found in configuration")
            
            config_models = {model['name'] for model in ollama_client.get('models', [])}
            logging.debug("ollama models: %s", config_models)

            # Step 3: Add new models from Ollama to config
            for model_name in ollama_models:
                if model_name not in config_models:
                    ollama_client['models'].append({
                        'name': model_name,
                        'max_input_tokens': 128000  # Default value from existing config
                    })

            # Step 4: Remove models from config that are not in Ollama
            ollama_client['models'] = [
                model for model in ollama_client['models']
                if model['name'] in ollama_models
            ]

            # Step 5: Update the config file
            self.update_config(self.config)
            logging.info("Updated %s with current Ollama models %s", "file", ollama_client)
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Error executing docker command: {e}")
        except Exception as e:
            logging.error(f"Error updating configuration: {e}")

            

