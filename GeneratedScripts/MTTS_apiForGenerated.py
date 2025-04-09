import os
import random
import sys
from typing import Sequence, Mapping, Any, Union
import torch
import logging
def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Returns the value at the given index of a sequence or mapping.

    If the object is a sequence (like list or string), returns the value at the given index.
    If the object is a mapping (like a dictionary), returns the value at the index-th key.

    Some return a dictionary, in these cases, we look for the "results" key
    
    Args:
        obj (Union[Sequence, Mapping]): The object to retrieve the value from.
        index (int): The index of the value to retrieve.
    
    Returns:
        Any: The value at the given index.
    
    Raises:
        IndexError: If the index is out of bounds for the object and the object is not a mapping.
    """
    try:
        return obj[index]
    except KeyError:
        return obj['result'][index]


def find_path(name: str, path: str = None) -> str:
    """
    Recursively looks at parent folders starting from the given path until it finds the given name. 
    Returns the path as a Path object if found, or None otherwise.
    """
    # If no path is given, use the current working directory
    if path is None:
        path = os.getcwd()
    
    # Check if the current directory contains the name
    if name in os.listdir(path):
        path_name = os.path.join(path, name)
        print(f"{name} found: {path_name}")
        return path_name

    # Get the parent directory
    parent_directory = os.path.dirname(path)

    # If the parent directory is the same as the current directory, we've reached the root and stop the search
    if parent_directory == path:
        return None

    # Recursively call the function with the parent directory
    return find_path(name, parent_directory)


def add_comfyui_directory_to_sys_path() -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    comfyui_path = find_path('ComfyUI')
    if comfyui_path is not None and os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        print(f"'{comfyui_path}' added to sys.path")





add_comfyui_directory_to_sys_path()



def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    import asyncio
    import execution
    from nodes import init_extra_nodes
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Creating an instance of PromptServer with the loop
    server_instance = server.PromptServer(loop)
    execution.PromptQueue(server_instance)

    # Initializing custom nodes
    init_extra_nodes()

with open('processed.txt', 'r', encoding='utf-8') as file:
    content = file.read()
    
import re
from nodes import NODE_CLASS_MAPPINGS

def main():
   
    # Configure logging
    # Add path to parent directory to import helper
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from helper import setup_script_logging
    # Set up logger
    logger = setup_script_logging('AudioProcessor')
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    config_file = os.path.join(parent_dir, "CONFIG.txt")
    try:
        logger.info(f"Looking for CONFIG.txt at: {config_file}")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('voice='):
                        custom_voice = line.strip().split('=', 1)[1].strip()
                        # Remove quotes if present
                        if custom_voice.startswith('"') and custom_voice.endswith('"'):
                            custom_voice = custom_voice[1:-1]
                        elif custom_voice.startswith("'") and custom_voice.endswith("'"):
                            custom_voice = custom_voice[1:-1]
                        logger.info(f"Found custom output directory in CONFIG.txt: {custom_voice}")
                        break

    except Exception as e:
        logger.warning(f"Error reading CONFIG.txt: {str(e)}")
        custom_voice = 'en-US:Steffan(Male)'
        logger.warning("Using default voice: en-US:Steffan(Male)")
        
    # Split the content into sentences
    sentences = re.split(r'(?<=[.!?])\s+', content)
    import_custom_nodes()
    with torch.inference_mode():
        logger.info("Generating audio for the processed text with VOICE: " + custom_voice)
        microsoftspeech_tts = NODE_CLASS_MAPPINGS["MicrosoftSpeech_TTS"]()
        
        # Generate audio for each sentence
        for i, sentence in enumerate(sentences):
            if not sentence.strip():  # Skip empty sentences
                continue
            logging.info(f"Generating audio for sentence {i + 1}/{len(sentences)}: {sentence.strip()}")   
            filename_prefix = f"comfyUIVoiceTTK_sentence_"
            microsoftspeech_tts.text_2_audio(
                voice=custom_voice, 
                rate=0, 
                filename_prefix=filename_prefix, 
                text=sentence.strip()
            )

if __name__ == "__main__":
    import os
    def delete_files_in_directory(directory: str) -> None:
        """Deletes all files in the given directory."""
        for file_name in os.listdir(directory):
            file_path = os.path.join(directory, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    # Get the parent directory of the current file
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    # Navigate to the ComfyUI output audio directory from the parent directory
    audio_directory = os.path.join(os.path.dirname(parent_dir), "ComfyUI", "output", "audio")
    delete_files_in_directory(audio_directory)
    main()
