# Ollama CLI Chat

A simple Python-based command-line interface (CLI) for chatting with an Ollama server.

## Motivation

I created this project primarily to experiment with Ollama while building a quick terminal-based chat tool to streamline my workflow. Opening a web browser can feel sluggish, so this CLI provides a faster alternative for instant interactions. For instance, while working on vim it's specially useful.

For in-depth research tasks, I recommend using online LLM chats, as they often offer better rendering and formatting. However, for quick questions and answers, the terminal is my go-to choice—it's lightweight and efficient.

## Performance Notes

For reference, I'm running Ollama on a server equipped with an RTX 4080 GPU. Response times are quite acceptable with Llama models, making them ideal for tasks like querying commands, generating script snippets, or other short-form assistance.

In comparison, using GPT-OSS models is noticeably slower but tends to produce more comprehensive and detailed answers. Llama strikes a good balance for my everyday needs.

## Usage Tips

To make the tool more accessible, I created a symlink in `/usr/bin` pointing to the script. This allows me to execute it from anywhere in the terminal without specifying the full path. You can do the same after installing:

```bash
sudo ln -s /path/to/your/script.py /usr/bin/ollama-chat
```

Then, simply run `ollama-chat` to start chatting!
