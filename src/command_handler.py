import os
from src.llmclient import LLMClient
from src.config_manager import ConfigManager
import logging

class CommandHandler:
    def __init__(self, config_manager: ConfigManager, llm_client: 'LLMClient'):
        self.commands = {
            ':exit': (self._exit, "Quit the program"),
            ':q': (self._exit, "Also quit the program"),
            ':help': (self._help, "Print help"),
            ':clear': (self._clear, "Clear the screen"),
            ':models': (self._models, "List and select a model"),
            ':updateollama': (self._update_ollama_models, "Update config file with pulled ollama models"),
            ':set': (self._set, "Set some features on or off"),
            ':role': (self._role, "Change the role of the assistant"),
            ':listroles': (self._list_roles, "List the existing roles")
        }
        self.args = []
        self.config_manager = config_manager
        self.llm_client = llm_client
        self.logger = logging.getlogger('llmchat.configmanager')

    def _exit(self):
        print("Bye!")
        return False

    def _help(self):
        print("\n")
        for command, value in self.commands.items():
            print(f"{command} -> {value[1]}")
        return True

    def _clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        return True

    def _models(self):
        models = self.llm_client.list_models()
        selected_model = questionary.select(
            "Select a model:",
            choices = models,
            default = llm_client.get_current_model()
        ).ask()
        self.llm_client.load_model(selected_model)
        return True

    def _set(self):
        global TIMING
        global MARKDOWN
        if not self.args:
            print("set options: timing, notiming, markdown, nomarkdown")
            return True
        TIMING = (TIMING and not (self.args[0] == "notiming")
                 or self.args[0] == "timing")

        MARKDOWN = (MARKDOWN and not (self.args[0] == "nomarkdown")
                 or self.args[0] == "markdown")
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
            return self._list_roles()
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
        if not len(user_input):
            return True
        command, *self.args = user_input.strip().split(maxsplit=1)
        self.args = self.args[0].split() if self.args else []
        if command.startswith(":"):
            action, _ = self.commands.get(command, self._unknown_command)
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
                
                if MARKDOWN:
                    md = Markdown(response)
                else:
                    md = response
                with console.pager(styles=True, links=True):
                    console.print(md)
                
            except Exception as e:
                logger.error(f"Error: {e}")
            return True


