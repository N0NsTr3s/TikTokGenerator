import os
import random
from re import sub
import sys
from typing import Sequence, Mapping, Any, Union
from librosa import ex
import torch
import subprocess
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging

parser=argparse.ArgumentParser(description='Run a series of scripts in sequence.')
parser.add_argument('--add-minigame', choices=['True', 'False'], default='False', help='Modify the hight of the picture if there is a minigame or not in the video (True/False)')
args = parser.parse_args()


if args.add_minigame == 'True':
    picture_hight = 960
else:
    picture_hight = 1920

# Replace your existing logger creation with:
logger = setup_script_logging(__name__)

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
        return obj["result"][index] # type: ignore


def find_path(name: str, path: str = None) -> str: # pyright: ignore[reportArgumentType]
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
        logger.info(f"{name} found: {path_name}")
        return path_name

    # Get the parent directory
    parent_directory = os.path.dirname(path)

    # If the parent directory is the same as the current directory, we've reached the root and stop the search
    if parent_directory == path:
        return None # type: ignore

    # Recursively call the function with the parent directory
    return find_path(name, parent_directory)


def add_comfyui_directory_to_sys_path() -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    comfyui_path = find_path("ComfyUI")
    if comfyui_path is not None and os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        logger.info(f"'{comfyui_path}' added to sys.path")





add_comfyui_directory_to_sys_path()
try:
    import parsetextForGenerated
    parsetextForGenerated.main()
    logger.info("parsetextForGenerated.py executed successfully")
except:
    logger.info("Running parsetextForGenerated.py directly failed. Subrunning it now.")
    subprocess.run(["python", "GeneratedScripts\\parsetextForGenerated.py"])

from nodes import (
    SaveImage,
    CLIPTextEncode,
    NODE_CLASS_MAPPINGS,
    VAEDecode,
    CheckpointLoaderSimple,
    EmptyLatentImage,
    VAELoader,
    KSampler,
)


lines = open("promptCheck.txt", "r").read()


emptylatentimage = EmptyLatentImage()
emptylatentimage_5 = emptylatentimage.generate(
    width=1280, height=picture_hight, batch_size=1
)

checkpointloadersimple = CheckpointLoaderSimple()
checkpointloadersimple_4 = checkpointloadersimple.load_checkpoint(
    ckpt_name="forrealxlV10_v10.safetensors"
)


vaeloader = VAELoader()
vaeloader_10 = vaeloader.load_vae(vae_name="sdxl_vae.safetensors")

ksampler = KSampler()
vaedecode = VAEDecode()
saveimage = SaveImage()
def main():
    for line in lines.split('\n')[:-1]:
        logger.info("Generated Image Prompt: " + line)

        with torch.inference_mode():
           


            cliptextencode = CLIPTextEncode()
            cliptextencode_6 = cliptextencode.encode(
                text=line,
                clip=get_value_at_index(checkpointloadersimple_4, 1),
            )

            cliptextencode_7 = cliptextencode.encode(
                text="text, watermark, ugly face, mutated hands, low res, blurry face, watermark, title, signature,  NegativeDynamics, negative_hand, monochrome, ugly face, names logo, nsfw, faces, nudes, nude, naked, nipples, face, flag, gay, lesbian, homosexuality",
                clip=get_value_at_index(checkpointloadersimple_4, 1),
            )
        
            ksampler_3 = ksampler.sample(
                seed=random.randint(1, 2**64),
                steps=20,
                cfg=2.0,
                sampler_name="dpmpp_3m_sde",
                scheduler="karras",
                denoise=1,
                model=get_value_at_index(checkpointloadersimple_4, 0),
                positive=get_value_at_index(cliptextencode_6, 0),
                negative=get_value_at_index(cliptextencode_7, 0),
                latent_image=get_value_at_index(emptylatentimage_5, 0),
            )

            vaedecode_8 = vaedecode.decode(
                samples=get_value_at_index(ksampler_3, 0),
                vae=get_value_at_index(vaeloader_10, 0),
            )

            saveimage_9 = saveimage.save_images(
                filename_prefix="ComfyUITikTok", images=get_value_at_index(vaedecode_8, 0)
            )


if __name__ == "__main__":
    def delete_images_with_prefix(prefix: str) -> None:
        """
        Deletes all images in the current directory that have the given prefix.
        """
        comfyui_dir = find_path("ComfyUI")
        if comfyui_dir is None:
            logger.error("ComfyUI folder not found")
            raise Exception("ComfyUI folder not found")
        output_dir = os.path.join(comfyui_dir, "output")
        if not os.path.exists(output_dir):
            logger.error("Output folder not found at: " + output_dir)
            raise Exception("Output folder not found at: " + output_dir)
        for file_name in os.listdir(output_dir):
            if file_name.startswith(prefix):
                file_path = os.path.join(output_dir, file_name)  # Get the full path of the file
                os.remove(file_path)
                logger.info(f"Deleted image: {file_path}")

    delete_images_with_prefix("ComfyUITikTok")
    main()
