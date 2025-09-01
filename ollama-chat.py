#!/usr/bin/env python3

import requests
import json
import time
import timeit
import sys
import argparse
import questionary
from rich.console import Console
from rich.markdown import Markdown

console = Console()

def response_generator(msg_content):
    lines = msg_content.split('\n')
    for line in lines:
        words = line.split()
        for word in words:
            yield word + " "
            time.sleep(0.1)
        yield "\n"

def chat(messages, model):
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        )
        response.raise_for_status()
        output = ""
        for line in response.iter_lines():
            body = json.loads(line)
            if "error" in body:
                raise Exception(body["error"])
            if body.get("done", False):
                return {"role": "assistant", "content": output}
            output += body.get("message", {}).get("content", "")
    except Exception as e:
        return {"role": "assistant", "content": str(e)}

def main():
    '''
    parser = argparse.ArgumentParser(description="Terminal-based Ollama Chat")
    parser.add_argument("--model", default="gpt-oss:20b", help="The model to use (default: gpt-oss:20b)")
    args = parser.parse_args()
    model = args.model
    '''
    print("Welcome to the ollama Chat Interface (Terminal Version). ")

    resp = requests.get("http://localhost:11434/api/tags")
    resp.raise_for_status()
    data = resp.json()

    models = [m["name"] for m in data.get("models", [])]
    if not models:
        print("No models found. Pull one via docker...")
        exit(1)
    
    model= questionary.select(
        "Available models:",
        choices = models).ask()

    messages = []

    while True:
        user_input = input("\n> ")
        if user_input.lower() == 'exit':
            print("Bye!")
            break
        
        messages.append({"role": "user", "content": user_input})
        start = timeit.default_timer()
        response = chat(messages, model)
        end = timeit.default_timer()
        messages.append({"role": "assistant", "content": response["content"]})
        
        md = Markdown(response["content"])
        console.print(md)
        console.print(f"[{end - start} sec.]")
        

if __name__ == "__main__":
    main()
