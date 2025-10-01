#!/usr/bin/env python3

import os
import sys, select
import argparse
import yaml
import timeit
import subprocess
from pathlib import Path
from src.xai_chat import XaiChat
from src.gemini_chat import GeminiChat
from src.base_chat import BaseChatClient
from src.openai_chat import OpenAiChat
from src.openai_compatible_chat import OpenAiCompatibleChat
from src.llmclient import LLMClient, RoleConfig
from src.config_manager import ConfigManager
from src.command_handler import CommandHandler
from typing import Dict, Any, List
from rich.console import Console
from rich.text import Text
import logging

TIMING = False
MARKDOWN = True

logger = logging.getLogger('llmchat')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


import builtins
import traceback
old_open = builtins.open
def logged_open(filename, mode='r', *args, **kwargs):
    if any(c in mode for c in 'wax+'):
        logger.warning(f"Opening {filename} in mode {mode}")
        logger.warning("Stack:\n" + ''.join(traceback.format_stack()))
    return old_open(filename, mode, *args, **kwargs)
builtins.open = logged_open


if __name__ == "__main__":
    os.environ.setdefault("PAGER", "less -RFX")

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', nargs=argparse.REMAINDER,
                        help='Ask the LLM only the question in the argument')
    args = parser.parse_args()
    
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
        logger.error(f"Error loading configuration: {e}")
        exit(1)
        
    if args.c:
        user_input=' '.join(args.c)
        command_handler.handle_input(user_input)
    else:
        st = True
        while st:
            prompt = Text("\n> ", style="white on @2f2430 bold")
            try:
                user_input = console.input(prompt)
                st = command_handler.handle_input(user_input)
            except Exception as e:
                logger.error(e)
