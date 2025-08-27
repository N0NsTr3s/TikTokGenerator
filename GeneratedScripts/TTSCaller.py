#!/usr/bin/env python3
"""Simple TTS caller that accepts text, voice, vibe and calls the local OPENAIFM node.

This script is a small wrapper intended to be invoked by the UI. It dynamically
loads the `openaifm.py` module from the ComfyUI custom node and calls OPENAIFM.generate.
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--text', help='Text to synthesize')
    p.add_argument('--text-file', help='Path to file containing text to synthesize')
    p.add_argument('--voice', required=True)
    p.add_argument('--vibe', default='---')
    p.add_argument('--optional-vibe-text', default='')
    args = p.parse_args()
    
    # Get text from either --text or --text-file
    if args.text_file:
        try:
            with open(args.text_file, 'r', encoding='utf-8') as f:
                text_content = f.read()
        except Exception as e:
            print(f'Error reading text file: {e}', file=sys.stderr)
            return 1
    elif args.text:
        text_content = args.text
    else:
        print('Either --text or --text-file must be provided', file=sys.stderr)
        return 1

    # Load local OpenAITTS helper if present
    try:
        import importlib.util
        openaitts_path = SCRIPT_DIR / 'OpenAITTS.py'
        if openaitts_path.exists():
            spec = importlib.util.spec_from_file_location('openaitts_local', str(openaitts_path))
            if spec and spec.loader:
                openaitts = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(openaitts)
            else:
                openaitts = None
        else:
            openaitts = None

        if openaitts is None or not hasattr(openaitts, 'load_openaifm_module'):
            print('Helper OpenAITTS.py or loader not found', file=sys.stderr)
            return 2

        openaifm_mod = openaitts.load_openaifm_module()
        if openaifm_mod is None or not hasattr(openaifm_mod, 'OPENAIFM'):
            print('Could not load openaifm module', file=sys.stderr)
            return 3

        node = openaifm_mod.OPENAIFM()

        # Split text into sentences similar to MTTS_apiForGenerated.py
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text_content)
        any_success = False
        for i, sentence in enumerate(sentences):
            s = sentence.strip()
            if not s or len(s) < 2:
                continue
            print(f'Generating sentence {i+1}/{len(sentences)}: {s[:60]}...')
            try:
                result = node.generate(s, args.voice, args.vibe, args.optional_vibe_text)
                # node.generate internally saves audio via save_audio_file
                if result is None:
                    print(f'Failed to generate sentence {i+1}', file=sys.stderr)
                else:
                    any_success = True
            except Exception as e:
                print(f'Error generating sentence {i+1}: {e}', file=sys.stderr)

        if any_success:
            print('Generation completed')
            return 0
        else:
            print('No sentences generated successfully', file=sys.stderr)
            return 4

    except Exception as e:
        print(f'Fatal error in TTSCaller: {e}', file=sys.stderr)
        return 5

def call_openai_tts(text, voice, vibe=None):
    """
    Call OpenAITTS.py CLI with the specified parameters
    
    Args:
        text (str): The text to convert to speech (mandatory)
        voice (str): The voice to use (mandatory)
        vibe (str, optional): The vibe/style to apply
    """
    cmd = ["python", "OpenAITTS.py", "--text", text, "--voice", voice]
    
    if vibe:
        cmd.extend(["--vibe", vibe])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("TTS generation successful!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error calling OpenAITTS.py: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False

def main_alt():
    parser = argparse.ArgumentParser(description="Call OpenAITTS.py with specified parameters")
    parser.add_argument("--text", required=True, help="Text to convert to speech")
    parser.add_argument("--play-voice", required=True, help="Voice to use for TTS")
    parser.add_argument("--vibe", help="Optional vibe/style to apply")
    
    args = parser.parse_args()
    
    success = call_openai_tts(args.text, args.voice, args.vibe)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    raise SystemExit(main())