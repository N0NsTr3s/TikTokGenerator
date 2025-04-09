import os
import glob
import cv2
import numpy as np
import torch
import subprocess
import argparse
import re
import gc
import logging


import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helper import setup_script_logging
# Configure logging

logger = setup_script_logging('VideoProcessor')

parser=argparse.ArgumentParser(description='Run a series of scripts in sequence.')
parser.add_argument('--add-minigame', choices=['True', 'False'], default='False', help='Add a minigame to the video (True/False)')
args = parser.parse_args()


# Set up paths
base_dir = os.getcwd()
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# Locate image directory
image_dir = os.path.join(os.path.dirname(parent_dir), "ComfyUI", "output")
logger.info(image_dir)
if not os.path.isdir(image_dir):
    raise FileNotFoundError(f"Image directory not found: {image_dir}")

# Locate audio directory (must be a subfolder of image_dir)
audio_dir = os.path.join(image_dir, "audio")
logger.info(audio_dir)
if not os.path.isdir(audio_dir):
    raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

# Locate the subtitles text file using glob
subtitles_files = glob.glob(os.path.join(parent_dir, "processed.txt"))
logger.info(subtitles_files)
if not subtitles_files:
    raise FileNotFoundError("Subtitles text file not found.")
subtitles_txt = subtitles_files[0]
logger.info(f"Subtitles text file: {subtitles_txt}")

# Define final video output location
final_output = os.path.join(parent_dir,"ComfyUI","Output","final_video.mp4")

# Define temporary directory for ffmpeg process
temp_dir = os.path.join(image_dir, "temp_ffmpeg")
os.makedirs(temp_dir, exist_ok=True)



# Read output directory from CONFIG.txt in parent directory
config_file = os.path.join(parent_dir, "CONFIG.txt")
zoom_factor = None

try:
    logger.info(f"Looking for CONFIG.txt at: {config_file}")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            for line in f:
                if line.strip().startswith('zoom_factor='):
                    zoom_factor = line.strip().split('=', 1)[1].strip()
                    # Remove quotes if present
                    if zoom_factor.startswith('"') and zoom_factor.endswith('"'):
                        zoom_factor = zoom_factor[1:-1]
                    elif zoom_factor.startswith("'") and zoom_factor.endswith("'"):
                        zoom_factor = zoom_factor[1:-1]
                    logger.info(f"Found custom Zoom Factor in CONFIG.txt: {zoom_factor}")
                    break

except Exception as e:
    logger.warning(f"Error reading CONFIG.txt: {str(e)}")
    logger.warning("Using default zoom factor")
    zoom_factor = 1.25

zoom_factor = float(zoom_factor)
logger.info(f"Using zoom factor: {zoom_factor}")
# Define global constants
  # Adjust this value as needed for the zoom effect

def detect_hardware_encoder():
    """Detect available hardware encoder for FFmpeg"""
    encoders = {
        "nvidia": {"encoder": "h264_nvenc", "device": "cuda", "init_options": ["-hwaccel", "cuda"]},
        "amd": {"encoder": "h264_amf", "device": "amf", "init_options": []},
        "intel": {"encoder": "h264_qsv", "device": "qsv", "init_options": ["-hwaccel", "qsv"]},
        "cpu": {"encoder": "libx264", "device": "cpu", "init_options": []}
    }
    
    # Check NVIDIA GPU
    if torch.cuda.is_available():
        logger.info("NVIDIA GPU detected, using NVENC hardware acceleration")
        return encoders["nvidia"]
    
    # Check for other encoders by testing them with FFmpeg
    for name, config in encoders.items():
        if name == "cpu":
            continue  # Skip checking CPU
        try:
            cmd = ["ffmpeg", "-encoders"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if config["encoder"] in result.stdout:
                logger.info(f"{name.upper()} hardware encoder detected, using {config['encoder']}")
                return config
        except:
            pass
    
    logger.info("No hardware encoders found, using CPU encoding")
    return encoders["cpu"]

# Get hardware encoder configuration
hw_encoder = detect_hardware_encoder()

# Set up device for PyTorch operations
device = torch.device(hw_encoder["device"] if hw_encoder["device"] == "cuda" else "cpu")
logger.info(f"Using device: {device}")

def create_zoom_video(image_file, output_video, duration=10, fps=30, zoom_limit=1.5, resolution="1280x720"):
    """
    Create a zoom effect video from a single image using FFmpeg's zoompan filter.
    
    Parameters:
        image_file (str): Path to the input image.
        output_video (str): Path for the output video.
        duration (int|float): Desired duration of the video in seconds.
        fps (int): Frame rate of the output video.
        zoom_limit (float): Maximum zoom factor.
        resolution (str): Output resolution as "widthxheight" (e.g., "1280x720").
    """
    
    # The number of frames determines how long each zoom step lasts.
    # 'd' in zoompan is set to the number of frames per zoom step.
    total_frames = int(duration * fps)
    # Experiment with the zoom speed. Here, the expression increases zoom until it reaches zoom_limit.
    zoom_expr = f"min(zoom+0.0015,{zoom_limit})"
    # Build the zoompan filter. Force the original aspect ratio to decrease if needed.
    vf_filter = f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution},fps={fps}"
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",                # Loop the image infinitely.
        "-i", image_file,
        "-vf", vf_filter,
        "-c:v", "libx264",           # Use H.264 codec, can change to your hardware encoder if needed.
        "-t", str(duration),         # Set the video duration.
        "-pix_fmt", "yuv420p",       # Ensure broad playback compatibility.
        output_video
    ]
    
    subprocess.run(cmd, check=True)
    
# Example usage:
# create_zoom_video("image.jpg", "output_zoom.mp4", duration=10, fps=30, zoom_limit=1.5, resolution="1280x720")

# Locate source images and voice-over files
image_files = []
for filename in os.listdir(image_dir):
    if filename.lower().endswith('.png') and 'ComfyUITikTok' in filename:
        image_files.append(os.path.join(image_dir, filename))
image_files.sort()
logger.info(f"Found {len(image_files)} image files.")

# Get all audio files
audio_files = []
for filename in os.listdir(audio_dir):
    if filename.lower().endswith('.mp3'):
        audio_files.append(os.path.join(audio_dir, filename))
audio_files.sort()
if not audio_files:
    raise FileNotFoundError("No voice-over files found.")
logger.info(f"Found {len(audio_files)} audio files.")

# Get the total duration of all audio files
total_audio_duration = 0
audio_durations = []
for audio in audio_files:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    audio_duration = float(result.stdout.strip())
    audio_durations.append(audio_duration)
    total_audio_duration += audio_duration

logger.info(f"Total audio duration: {total_audio_duration:.3f} seconds")

def process_image(image_file, idx):
    logger.info(f"Processing image {idx+1}/{len(image_files)}: {image_file}")
    
    try:
        # Use calculated duration for this specific clip
        clip_duration = total_audio_duration/len(image_files)
        
        # Create a temporary folder for this clip
        clip_frames_dir = os.path.join(temp_dir, f"clip_{idx:03d}")
        os.makedirs(clip_frames_dir, exist_ok=True)
        
        # Define output path for the zoom video clip
        clip_video = os.path.join(temp_dir, f"clip_{idx:03d}.mp4")
        if args.add_minigame=="True":
            # Create the zoom video directly using FFmpeg
            create_zoom_video(
                image_file=image_file,
                output_video=clip_video,
                duration=clip_duration,
                fps=60,
                zoom_limit=zoom_factor,  # Using the zoom_factor from config
                resolution="1280x960"
            )
        else:
            create_zoom_video(
                image_file=image_file,
                output_video=clip_video,
                duration=clip_duration,
                fps=60,
                zoom_limit=zoom_factor,  # Using the zoom_factor from config
                resolution="1280x1920"
            )
            
        logger.info(f"Created zoom clip: {clip_video}")
        return clip_video
        
    except Exception as e:
        logger.error(f"Error processing image {image_file}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Replace the ThreadPoolExecutor with sequential processing
clip_videos = []
logger.info("Processing images sequentially to avoid memory errors...")
for idx, img in enumerate(image_files):
    # Force cleanup before processing each image
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Process one image at a time
    clip_video = process_image(img, idx)
    if clip_video:
        clip_videos.append(clip_video)
    
    # Force another cleanup after processing
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

if not clip_videos:
    raise ValueError("No clip videos were created.")

# Concatenate all clip videos using FFmpeg concat demuxer
concat_list = os.path.join(temp_dir, "concat_list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for clip in sorted(clip_videos):
        # Use forward slashes in the file path for FFmpeg
        f.write(f"file '{clip.replace(os.sep, '/')}'\n")
temp_video = os.path.join(temp_dir, "temp_video.mp4")
ffmpeg_concat = [
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c", "copy", temp_video
]
subprocess.run(ffmpeg_concat, check=True)
logger.info("Concatenated clips into video: %s", temp_video)

# Concatenate all audio files and add to the concatenated video
temp_audio_concat = os.path.join(temp_dir, "audio_combined.mp3")

# Create a file list for audio concatenation
audio_concat_list = os.path.join(temp_dir, "audio_concat_list.txt")
with open(audio_concat_list, "w", encoding="utf-8") as f:
    for audio in audio_files:
        # Use forward slashes in the file path for FFmpeg
        f.write(f"file '{audio.replace(os.sep, '/')}'\n")

# Concatenate all audio files
ffmpeg_audio_concat = [
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", audio_concat_list,
    "-c", "copy", temp_audio_concat
]
subprocess.run(ffmpeg_audio_concat, check=True)
logger.info("Concatenated audio files: %s", temp_audio_concat)

# Add the concatenated audio to the video
temp_video_audio = os.path.join(temp_dir, "temp_video_with_audio.mp4")
ffmpeg_audio = [
    "ffmpeg", "-y",
    "-i", temp_video,
    "-i", temp_audio_concat,
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-crf", "18",
    "-shortest",
    temp_video_audio
]
subprocess.run(ffmpeg_audio, check=True)
logger.info("Added audio to video: %s", temp_video_audio)

# Generate an SRT subtitles file from your processed.txt using audio file durations
srt_file = "subtitles.srt"

def format_time(seconds):
    """Format time as HH:MM:SS,mmm for SRT files."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}".replace(".", ",")

def write_srt_file(subtitle_timings, output_file):
    """Write the SRT file with the calculated timings."""
    with open(output_file, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(subtitle_timings):
            f.write(f"{i+1}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n")
    
    logger.info(f"Generated fixed SRT subtitles: {output_file}")

def split_into_sentences(text):
    """Split text into sentences based on common sentence ending punctuation."""
    # Split on period, exclamation mark, or question mark followed by space or end of string
    sentences = re.split(r'(?<=[.!?])\s+|(?<=[.!?])$', text)
    # Remove empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

def generate_srt_from_audio_files(text_file, audio_files, audio_durations, output_srt):
    """Generate SRT with timing based on individual audio file durations."""
    # Read the entire text content
    with open(text_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split the content into sentences
    sentences = split_into_sentences(content)
    
    # Ensure we have the same number of sentences and audio files
    if len(sentences) != len(audio_files):
        logger.warning(f"Number of sentences ({len(sentences)}) doesn't match number of audio files ({len(audio_files)})")
        # Use the smaller number
        count = min(len(sentences), len(audio_files))
        sentences = sentences[:count]
        audio_files = audio_files[:count]
        audio_durations = audio_durations[:count]
    
    # Calculate cumulative start times
    start_times = [0]
    for duration in audio_durations[:-1]:
        start_times.append(start_times[-1] + duration)
    
    # Generate subtitle timings
    subtitle_timings = []
    for i, (text, duration) in enumerate(zip(sentences, audio_durations)):
        start_time = start_times[i]
        end_time = start_time + duration
        subtitle_timings.append((start_time, end_time, text))
    
    # Write SRT file
    write_srt_file(subtitle_timings, output_srt)
    
    return output_srt

# Generate fixed subtitles
generate_srt_from_audio_files(subtitles_txt, audio_files, audio_durations, srt_file)
srt_ffmpeg = srt_file.replace("\\", "/")
temp_video_subs = os.path.join(temp_dir, "temp_video_with_subs.mp4")

# Get input video dimensions
probe_cmd = [
    "ffprobe", "-v", "error", 
    "-select_streams", "v:0", 
    "-show_entries", "stream=width,height", 
    "-of", "csv=p=0", 
    temp_video_audio
]
result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
dimensions = result.stdout.strip().split(',')
width, height = int(dimensions[0]), int(dimensions[1])

# Ensure dimensions are even (divisible by 2)
if width % 2 != 0:
    width += 1
if height % 2 != 0:
    height += 1

# Burn subtitles with explicit output dimensions to ensure they're even
ffmpeg_subs = [
    "ffmpeg", "-y",
    "-i", temp_video_audio,
    "-vf", f"subtitles='{srt_ffmpeg}',scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
    "-c:v", hw_encoder["encoder"],
    "-c:a", "copy",
    temp_video_subs
]
subprocess.run(ffmpeg_subs, check=True)
logger.info("Burned subtitles into video: %s", temp_video_subs)




import math
# Load the last video from the Videos folder and stack vertically if add-minigame is specified
if args.add_minigame=="True":
    # Find the video folder Minigames\output with the os library
    current_dir = os.getcwd()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    videos_folder = os.path.join(current_dir, "Minigames", "output")
    videos = sorted(glob.glob(os.path.join(videos_folder, "*.avi")))
    if not videos:
        raise FileNotFoundError("No video files found in the 'Videos' folder.")
    
    # Sort videos by modification time (newest first)
    videos.sort(key=os.path.getmtime, reverse=True)
    logger.info(f"Found {len(videos)} minigame videos")
    
    # Get main video duration
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", temp_video_subs
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    main_video_duration = float(result.stdout.strip())
    logger.info(f"Main video duration: {main_video_duration:.2f}s")
    
    # Add videos from newest to oldest until we exceed the main video duration
    total_minigame_duration = 0
    selected_videos = []
    
    for video in videos:
        # Get minigame video duration
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout_content = result.stdout.strip()
            if not stdout_content:
                logger.error(f"Empty ffprobe output for {video}")
                video_duration = 5.0  # Default duration if ffprobe fails
                logger.warning(f"Using default duration of {video_duration}s")
            else:
                video_duration = float(stdout_content)
        except ValueError as e:
            logger.error(f"Failed to parse duration for {video}: {str(e)}, output: '{result.stdout}'")
            logger.error(f"ffprobe stderr: {result.stderr}")
            video_duration = 5.0  # Default duration if parsing fails
            logger.warning(f"Using default duration of {video_duration}s")
        
        selected_videos.append((video, video_duration))
        total_minigame_duration += video_duration
        logger.info(f"Added minigame video: {video} ({video_duration:.2f}s)")
        
        if total_minigame_duration >= main_video_duration:
            break
    
    logger.info(f"Selected {len(selected_videos)} minigame videos with total duration: {total_minigame_duration:.2f}s")
    
    # If we still don't have enough duration, loop the oldest video
    if total_minigame_duration < main_video_duration and selected_videos:
        logger.info("Still need more duration, will loop the oldest selected video if needed")
        oldest_video, oldest_duration = selected_videos[-1]
        remaining_duration = main_video_duration - total_minigame_duration
        additional_loops = math.ceil(remaining_duration / oldest_duration)
        
        for _ in range(additional_loops):
            selected_videos.append((oldest_video, oldest_duration))
            total_minigame_duration += oldest_duration
            
        logger.info(f"Added {additional_loops} loops of the oldest video. Total duration: {total_minigame_duration:.2f}s")
    
    # Create a concat file for the selected videos
    minigame_concat_list = os.path.join(temp_dir, "minigame_concat_list.txt")
    with open(minigame_concat_list, "w", encoding="utf-8") as f:
        for video, _ in selected_videos:
            f.write(f"file '{video.replace(os.sep, '/')}'\n")
    
    # Create concatenated minigame video
    minigame_input = os.path.join(temp_dir, "concatenated_minigame.mp4")
    ffmpeg_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", minigame_concat_list,
        "-c", "copy",
        minigame_input
    ]
    subprocess.run(ffmpeg_concat, check=True)
    logger.info(f"Created concatenated minigame video: {minigame_input}")

# We'll use FFmpeg filter_complex to scale and stack videos vertically if minigame is added
final_temp = os.path.join(temp_dir, "final_combined.mp4")

if args.add_minigame=="True":
    logger.info("Stacking videos vertically...")
    logger.debug("temp_video_subs: %s", temp_video_subs)
    logger.debug("minigame_input: %s", minigame_input)
    encoder_name=hw_encoder['encoder']
    logger.debug("encoder_name: %s", encoder_name)
    
    # Remove the 'shortest' flag to use the full duration of both videos
    ffmpeg_stack = f'ffmpeg -y -i {temp_video_subs} -i {minigame_input} -filter_complex "[0:v]scale=1280:960[v0];[1:v]scale=1280:960[v1];[v0][v1]vstack=inputs=2[v]" -map "[v]" -map "0:a?" -c:v {encoder_name} -c:a aac -b:a 192k -t {main_video_duration} {final_temp}'
    
    subprocess.run(ffmpeg_stack, check=True)
    logger.info("Stacked videos vertically into: %s", final_temp)
else:
    logger.info("Using video with subtitles as final output (no minigame added)")
    # Just use the subtitled video as the final output if no minigame
    final_temp = temp_video_subs
    # Rename the file and update the path
    final_dir = os.path.dirname(final_temp)
    final_renamed = os.path.join(final_dir, "final_combined.mp4")
    
    # Check if file exists and remove it before renaming
    if os.path.exists(final_renamed):
        logger.warning(f"File {final_renamed} already exists, removing it...")
        os.remove(final_renamed)
    
    os.rename(final_temp, final_renamed)
    final_temp = final_renamed
    logger.info("Using video with subtitles as final output (no minigame added)")


    # Read output directory from CONFIG.txt in parent directory
    config_file = os.path.join(parent_dir, "CONFIG.txt")
    custom_output_dir = None

    try:
        logger.info(f"Looking for CONFIG.txt at: {config_file}")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('output_dir='):
                        custom_output_dir = line.strip().split('=', 1)[1].strip()
                        # Remove quotes if present
                        if custom_output_dir.startswith('"') and custom_output_dir.endswith('"'):
                            custom_output_dir = custom_output_dir[1:-1]
                        elif custom_output_dir.startswith("'") and custom_output_dir.endswith("'"):
                            custom_output_dir = custom_output_dir[1:-1]
                        logger.info(f"Found custom output directory in CONFIG.txt: {custom_output_dir}")
                        break
        
        if custom_output_dir:
            # Check if it's an absolute path
            if os.path.isabs(custom_output_dir):
                output_dir = custom_output_dir
            else:
                # If it's a relative path, make it relative to parent_dir
                output_dir = os.path.join(parent_dir, custom_output_dir)
        else:
            # Fallback to default output directory
            logger.warning("No output_dir found in CONFIG.txt, using default output directory")
            output_dir = os.path.join(parent_dir, "Output")
    except Exception as e:
        logger.warning(f"Error reading CONFIG.txt: {str(e)}")
        logger.warning("Using default output directory")
        output_dir = os.path.join(parent_dir, "Output")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Using output directory: {output_dir}")

# Move final combined video to the desired output location
logger.info(f"Final video saved at: {final_temp}")
logger.info(f"File size: {os.path.getsize(final_temp)} bytes")

# Move the final video to the Output folder in the parent directory
output_dir = os.path.join(parent_dir, "Output")
os.makedirs(output_dir, exist_ok=True)
final_output_path = os.path.join(output_dir, "final_video.mp4")
# (Optional) Clean up temporary files
import shutil
shutil.move(final_temp, final_output_path)
logger.info(f"Final video moved to: {final_output_path}")
