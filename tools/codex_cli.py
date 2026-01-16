#!/usr/bin/env python3
"""Simple CLI for sending prompts to an OpenAI Codex-style model.

Usage:
  echo "print('hello')" | python tools/codex_cli.py
  python tools/codex_cli.py --prompt "Write a Python function to..."
"""
import argparse
import os
import sys
import openai


def main():
    parser = argparse.ArgumentParser(description="Codex CLI")
    parser.add_argument("--prompt", "-p", help="Prompt text. If omitted, read from stdin.")
    parser.add_argument("--model", "-m", default=os.environ.get("OPENAI_MODEL", "code-davinci-002"), help="Model to use (env OPENAI_MODEL)")
    parser.add_argument("--max-tokens", "-k", type=int, default=256)
    parser.add_argument("--temperature", "-t", type=float, default=0.0)
    args = parser.parse_args()

    prompt = args.prompt
    if not prompt:
        prompt = sys.stdin.read()
        if not prompt:
            parser.error("No prompt provided via --prompt or stdin")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY is not set in environment", file=sys.stderr)
        sys.exit(2)

    openai.api_key = api_key

    try:
        resp = openai.Completion.create(
            model=args.model,
            prompt=prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            n=1,
            stop=None,
        )
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(3)

    text = resp.choices[0].text
    if text is None:
        print("<no output>")
    else:
        print(text.strip())


if __name__ == "__main__":
    main()
