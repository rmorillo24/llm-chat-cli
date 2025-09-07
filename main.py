import yaml
import timeit
from pathlib import Path
from clients import BaseChatClient, XaiChat, GeminiChat, OpenAiCompatibleChat, OpenAiChat
from typing import Dict, Any, List
from rich.console import Console
from rich.markdown import Markdown
import logging
logging.basicConfig(level=logging.DEBUG)
# logging.debug("Variable x = %s", x)

class LLMClient:
    def __init__(self, config_path: str):
        """Carga la configuración desde un archivo YAML y valida el modelo por defecto."""
        try:
            with open(config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                logging.debug("Loaded config: %s", self.config)
        except FileNotFoundError:
            raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error al parsear el archivo YAML: {e}")
        logging.debug("loading defaults")        
        self.clients = {client['type']: client for client in self.config.get('clients', [])}
        self.default_model = self.config.get('default', None)
        self.current_client: Optional[BaseChatClient] = None
        self.current_model: Optional[str] = None
        logging.debug("defaults loaded")

        # Validar el modelo por defecto (si existe)
        if self.default_model:
            provider, model_name = self.default_model.split(':') if ':' in self.default_model else (None, None)
            if not provider or not model_name:
                raise ValueError(f"Formato de 'default' inválido: {self.default_model}. Se espera 'provider:model'")
            if provider not in self.clients:
                raise ValueError(f"Proveedor por defecto {provider} no encontrado en la configuración")
            client_config = self.clients[provider]
            model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
            if not model_config:
                raise ValueError(f"Modelo por defecto {model_name} no encontrado para el proveedor {provider}")

    def load_model(self, model: str = None) -> None:
        """Carga el modelo especificado o el modelo por defecto."""
        model = model or self.default_model
        logging.debug("load_model -> loading model: %s", model)
        if not model:
            raise ValueError("No se especificó un modelo y no hay modelo por defecto en la configuración")

        provider, model_name = model.split(':') if ':' in model else (None, model)
        logging.debug("load_model -> proveedor: %s, model_name: %s", provider, model_name)
        if not provider or not model_name:
            raise ValueError(f"Formato de modelo inválido: {model}. Se espera 'provider:model'")
        if provider not in self.clients:
            raise ValueError(f"Proveedor {provider} no encontrado en la configuración")

        client_config = self.clients[provider]
        model_config = next((m for m in client_config.get('models', []) if m['name'] == model_name), None)
        if not model_config:
            raise ValueError(f"Modelo {model_name} no encontrado para el proveedor {provider}")

        # Crear el cliente basado en el proveedor
        if provider == 'grok':
            self.current_client = XaiChat(client_config, model_config)
        elif provider == 'gemini':
            self.current_client = GeminiChat(client_config, model_config)
        elif provider == 'openai':
            self.current_client = OpenAiChat(client_config, model_config)
        elif provider == 'openai-compatible':
            self.current_client = OpenAiCompatibleChat(client_config, model_config)
        else:
            raise ValueError(f"Tipo de proveedor {provider} no soportado")

        self.current_model = model

    def send_message(self, messages: List[Dict[str, str]], temperature: float = 1.0) -> str:
        """Envía un mensaje usando el modelo actualmente cargado."""
        if self.current_client is None:
            raise ValueError("No se ha cargado ningún modelo. Llame a load_model primero.")
        return self.current_client.send_message(messages, temperature)



if __name__ == "__main__":
    # Ruta al archivo de configuración
    config_path = Path("configs.yaml")

    console = Console()

    # Cargar configuración y crear cliente
    try:
        llm_client = LLMClient(config_path)
        print(f"\nCargando el modelo por defecto ({llm_client.default_model})...")
        llm_client.load_model()  # Carga el modelo por defecto
    except Exception as e:
        print(f"Error al cargar la configuración: {e}")
        exit(1)
        
    messages = [
        {'role': 'system', 'content': 'Eres un asistente útil.'},
    ]

    while True:
        user_input = input("\n> ")
        if user_input.lower() == 'exit':
            print("Bye!")
            break
        print("\r", end="")
        
        try:
            messages.append({"role": "user", "content": user_input})
            start = timeit.default_timer()
            response = llm_client.send_message(messages)
            end = timeit.default_timer()
            #messages.append({"role": "assistant", "content": response["content"]})
            messages.append({"role": "assistant", "content": response})
            
            # md = Markdown(response["content"])
            md = Markdown(response)
            header = Markdown("| **" + user_input + "** |\n---\n\n\n")
            
            '''
            with console.pager(): # not using it because pager doesn't render properly the markdown
            '''
    
            console.print(header)
            console.print(md)
            console.print(f"\n[{str(end - start)}] sec.]")

        except Exception as e:
            print(f"Error con {model}: {e}")
