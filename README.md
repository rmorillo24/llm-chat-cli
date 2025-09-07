# LLM Chat CLI

A simple Python-based command-line interface (CLI) for chatting with configurable LLM APIs

## Motivation

I started this project as a simple bash script to do quick queries to an LLM so I could get quick help in the terminal and VIM.
Then Moved to Python, and as it was getting complex, I look for existing alternatives. After finding the amazing [digoden/aichat](https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://github.com/sigoden/aichat&ved=2ahUKEwjjk_Dl78aPAxUwVqQEHWHzMr8QFnoECCgQAQ&usg=AOvVaw3mJgVPJqldMVDzVEP5JC3L) I decided to use some of it's ideas (it's Rust and I wanted python, and my own implementation).

## Usage Tips

To make the tool more accessible, I created a symlink in `/usr/bin` pointing to the 'main.py' script. This allows me to execute it from anywhere in the terminal without specifying the full path. Then, simply run `llm-chat-cli` to start chatting!

Configure your preferred LLM providers and start chatting.
If you are using ollama you can use the OpenAI compatible section.
