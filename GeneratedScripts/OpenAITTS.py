import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import importlib.util
import importlib.machinery

# Example TTS content
INPUT_TEXT = """Whoa, dude… sounds like a gnarly situation with your card. But hey, no worries, I got you.\n\nLemme just pull up your account real quick… alright, looks like the system flagged some charges—probably thought they were, like, suspicious or somethin'. Super lame, I know.\n\nBut good news, my friend! I can clear that up right now. Just gotta verify a couple things, and boom—you'll be back in business, ridin' that wave of sweet, sweet purchases.\n\nHang tight, take a deep breath… we'll have you sorted in no time. Sound good, dude?"""

INSTRUCTIONS = """Voice: Laid-back, mellow, and effortlessly cool, like a surfer who's never in a rush.\n\nTone: Relaxed and reassuring, keeping things light even when the customer is frustrated.\n\nSpeech Mannerisms: Uses casual, friendly phrasing with surfer slang like dude, gnarly, and boom to keep the conversation chill.\n\nPronunciation: Soft and drawn-out, with slightly stretched vowels and a naturally wavy rhythm in speech.\n\nTempo: Slow and easygoing, with a natural flow that never feels rushed, creating a calming effect."""


def find_openaifm_data_dir() -> Optional[Path]:
    """Try to locate the OpenAIFM module data directory that should contain voices.json.

    Strategies:
    - Try importing an installed `openaifm` module.
    - Walk upward from this script to find a `ComfyUI/custom_nodes/ComfyUI-OpenAI-FM/data` folder.
    Returns Path to the data dir or None.
    """
    #Walk up from current file to locate ComfyUI custom_nodes folder
    current = Path(__file__).resolve()
    for parent in current.parents:
        # check a few reasonable locations
        candidate = parent / "ComfyUI" / "custom_nodes" / "ComfyUI-OpenAI-FM" / "data"
        if candidate.exists():
            return candidate
        candidate2 = parent / "custom_nodes" / "ComfyUI-OpenAI-FM" / "data"
        if candidate2.exists():
            return candidate2
        # stop after a few levels to avoid long walks
        if parent == parent.parent:
            break

    return None


def load_voices_json(data_dir: Path) -> Optional[Any]:
    jf = data_dir / "voices.json"
    if not jf.exists():
        return None
    try:
        with jf.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_comfyui_root() -> Optional[Path]:
    """Walk up from this file to find a 'ComfyUI' folder and return its path."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "ComfyUI"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def read_config_voice() -> Optional[str]:
    """Read CONFIG.txt from repo root (one level up) and return voice= value if present."""
    try:
        parent_dir = Path(__file__).resolve().parent.parent
        cfg = parent_dir / "CONFIG.txt"
        if not cfg.exists():
            return None
        with cfg.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("voice="):
                    val = line.strip().split("=", 1)[1].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    return val
    except Exception:
        return None
    return None



def extract_urls_from_voices(voices: Any) -> List[str]:
    """Given the loaded voices.json structure, return a list of http/https URLs found in common fields."""
    urls: List[str] = []

    def scan_obj(obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    urls.append(v)
                else:
                    scan_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                scan_obj(item)

    scan_obj(voices)
    # dedupe while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def list_voice_names(voices: Any) -> List[str]:
    names: List[str] = []
    if voices is None:
        return names
    if isinstance(voices, dict):
        # common patterns: top-level list under 'voices' or dict of named voices
        if "voices" in voices and isinstance(voices["voices"], list):
            items = voices["voices"]
        else:
            # treat dict keys as names
            items = [voices]
    else:
        items = voices

    def try_name(o: Any) -> Optional[str]:
        if isinstance(o, dict):
            for key in ("name", "id", "label", "display", "voice"):
                if key in o and isinstance(o[key], str):
                    return o[key]
        return None

    if isinstance(items, list):
        for it in items:
            n = try_name(it)
            if n:
                names.append(n)
            elif isinstance(it, str):
                names.append(it)
    else:
        n = try_name(items)
        if n:
            names.append(n)

    return names


def download_url(url: str, dest_dir: Path) -> Optional[Path]:
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        # choose filename from URL
        filename = url.split("/")[-1].split("?")[0] or "file.bin"
        dest = dest_dir / filename
        # use urllib to avoid extra deps
        import urllib.request

        with urllib.request.urlopen(url) as resp, dest.open("wb") as out:
            out.write(resp.read())
        return dest
    except Exception:
        return None


def find_openaifm_module_file() -> Optional[Path]:
    """Find the path to openaifm.py inside a ComfyUI-OpenAI-FM custom node folder."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        cand = parent / "ComfyUI" / "custom_nodes" / "ComfyUI-OpenAI-FM" / "openaifm.py"
        if cand.exists():
            return cand
        cand2 = parent / "custom_nodes" / "ComfyUI-OpenAI-FM" / "openaifm.py"
        if cand2.exists():
            return cand2
        # also check sibling GeneratedScripts
        cand3 = parent / "GeneratedScripts" / "openaifm.py"
        if cand3.exists():
            return cand3
    return None


def load_openaifm_module() -> Optional[Any]:
    """Dynamically load the openaifm module from its file path and return the module object."""
    mod_file = find_openaifm_module_file()
    if not mod_file:
        return None
    try:
        spec = importlib.util.spec_from_file_location("openaifm_custom", str(mod_file))
        if spec is None:
            return None
        module = importlib.util.module_from_spec(spec)
        loader = getattr(spec, "loader", None)
        if loader is None:
            return None
        loader.exec_module(module)  # type: ignore[attr-defined]
        return module
    except Exception:
        return None


def generate_with_openaifm_node(text: str, voice: str, vibe: str = "---", optional_vibe_text: str = "") -> Optional[Dict[str, Any]]:
    """Call the OPENAIFM node's generate method and return the generated audio dict.

    Returns the node's return value dict like {"waveform": ..., "sample_rate": ...}
    """
    mod = load_openaifm_module()
    if mod is None:
        print("Could not locate or load openaifm module")
        return None
    if not hasattr(mod, "OPENAIFM"):
        print("Loaded module does not contain OPENAIFM class")
        return None
    try:
        node = mod.OPENAIFM()
        result = node.generate(text, voice, vibe, optional_vibe_text)
        # node.generate returns a tuple with dict as first element per ComfyUI convention
        if isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], dict):
            return result[0]
        return None
    except Exception as e:
        print(f"Error while calling OPENAIFM.generate: {e}")
        return None


def main_cli() -> None:
    p = argparse.ArgumentParser(description="OpenAI TTS example + OpenAIFM voices helper")
    p.add_argument("--list-voices", action="store_true", help="Locate OpenAIFM data and list available voice names")
    p.add_argument("--download-voices", nargs="?", const="./downloaded_voices", help="Download any URLs found in voices.json to the target folder (default: ./downloaded_voices)")
    p.add_argument("--play-voice", nargs="?", const="Shimmer", help="Play demo text using the specified voice name (default: Shimmer)")
    p.add_argument("--use-openaifm", action="store_true", help="Use the local OpenAIFM node (ComfyUI) to generate audio instead of remote SDKs")
    p.add_argument("--text", nargs="?", help="Text to synthesize; if omitted uses built-in demo text")
    p.add_argument("--vibe", nargs="?", default="---", help="Vibe/key from vibes.json to influence generation (optional)")
    p.add_argument("--optional-vibe-text", nargs="?", default="", help="Custom vibe prompt text to override vibe selection (optional)")
    args = p.parse_args()

    data_dir = find_openaifm_data_dir()
    voices = None
    if data_dir:
        voices = load_voices_json(data_dir)

    if args.list_voices:
        if not data_dir or voices is None:
            print("OpenAIFM voices.json not found; make sure ComfyUI-OpenAI-FM/data/voices.json exists")
            sys.exit(1)
        names = list_voice_names(voices)
        if not names:
            print("No voice names found in voices.json; printing raw structure:")
            print(json.dumps(voices, ensure_ascii=False, indent=2))
            return
        print("Voices found:")
        for n in names:
            print(" -", n)
        return

    if args.download_voices:
        if not data_dir or voices is None:
            print("OpenAIFM voices.json not found; cannot download")
            sys.exit(1)
        urls = extract_urls_from_voices(voices)
        if not urls:
            print("No download URLs found in voices.json")
            sys.exit(0)
        dest = Path(args.download_voices)
        print(f"Downloading {len(urls)} files to {dest}")
        for u in urls:
            print("->", u)
            out = download_url(u, dest)
            print("   saved:" if out else "   failed to download", out)
        return

    # Default: use OPENAIFM node if available or requested
    text_to_use = args.text or INPUT_TEXT
    voice_to_use = args.play_voice or read_config_voice() or "Shimmer"

    if args.use_openaifm:
        print(f"Using OpenAIFM node to generate audio with voice='{voice_to_use}'")
        res = generate_with_openaifm_node(text_to_use, voice_to_use, vibe=args.vibe or "---", optional_vibe_text=args.optional_vibe_text or "")
        if res is None:
            print("Generation failed or module not available")
            sys.exit(1)
        print("Generation returned:")
        print({k: type(v) for k, v in res.items()})
        sys.exit(0)

    # If OpenAIFM not requested, instruct user to use --use-openaifm
    print("No TTS backend selected. To use the local OpenAIFM node run with --use-openaifm. Other SDK paths were removed from this helper.")
    sys.exit(0)


if __name__ == "__main__":
    main_cli()