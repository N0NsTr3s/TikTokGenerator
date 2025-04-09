import os
import glob
import cv2
import numpy as np
import torch
import torchvision.transforms as transforms
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import time
import re
import os
import glob

# 1️⃣ Check for CUDA and set device
if not torch.cuda.is_available():
    raise EnvironmentError("CUDA is not available. Please run on a machine with a CUDA-enabled GPU.")
device = torch.device("cuda")
print(f"Using device: {device}")

# 2️⃣ Function to generate zoom frames (using PyTorch)
def generate_zoom_frames(image, zoom_factor, num_frames):
    frames = []
    h, w = image.shape[:2]
    image_tensor = transforms.ToTensor()(image).unsqueeze(0).to(device)
    for i in range(num_frames):
        # Linear interpolation between 1 and zoom_factor
        scale = 1 + (zoom_factor - 1) * (i / (num_frames - 1))
        new_w, new_h = int(w / scale), int(h / scale)
        x1 = max((w - new_w) // 2, 0)
        y1 = max((h - new_h) // 2, 0)
        x2 = min((w + new_w) // 2, w)
        y2 = min((h + new_h) // 2, h)
        cropped = image_tensor[:, :, y1:y2, x1:x2]
        zoomed = torch.nn.functional.interpolate(cropped, size=(h, w), mode='bilinear', align_corners=False)
        frame = (zoomed.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        frames.append(frame)
    return frames

# 3️⃣ Set up paths
# Define base directory for TikTokCreator files
base_dir = os.getcwd()
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# Locate image directory
image_dir = os.path.join(parent_dir, "ComfyUI", "output")
if not os.path.isdir(image_dir):
    raise FileNotFoundError(f"Image directory not found: {image_dir}")

# Locate audio directory (must be a subfolder of image_dir)
audio_dir = os.path.join(image_dir, "audio")
if not os.path.isdir(audio_dir):
    raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

# Locate the subtitles text file using glob
subtitles_files = glob.glob(os.path.join(base_dir, "processed.txt"))
if not subtitles_files:
    raise FileNotFoundError("Subtitles text file not found.")
subtitles_txt = subtitles_files[0]

# Define final video output location (using the current user's Desktop)
final_output = os.path.join(base_dir,"Output","final_video.mp4")

# Define temporary directory for ffmpeg process
temp_dir = os.path.join(image_dir, "temp_ffmpeg")
os.makedirs(temp_dir, exist_ok=True)

# 4️⃣ Locate source images and voice-over file
image_files = sorted(glob.glob(os.path.join(image_dir, "*ComfyUITikTok*.png")))
print(f"Found {len(image_files)} image files.")

audio_files = glob.glob(os.path.join(audio_dir, "*.mp3"))
if not audio_files:
    raise FileNotFoundError("No voice-over file found.")
audio_file = audio_files[0]
print(f"Audio file: {audio_file}")

# 5️⃣ Determine clip duration using audio duration (via ffprobe)
result = subprocess.run([
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", audio_file
], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
audio_duration = float(result.stdout.strip())
video_duration = audio_duration + 1.5
print(f"Video duration: {video_duration:.2f} seconds")
clip_duration = video_duration / len(image_files) if image_files else 0

zoom_factor = 1.5

# 6️⃣ Process each image to generate a video clip (using the zoom effect)
def process_image(image_file, idx):
    print(f"Processing image: {image_file}")
    image = cv2.imread(image_file)
    if image is None:
        print(f"Failed to load image: {image_file}")
        return None
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    num_frames = int(clip_duration * 60)  # assuming 30 fps
    frames = generate_zoom_frames(image, zoom_factor, num_frames)
    
    # Create a temporary folder for frames of this clip
    clip_frames_dir = os.path.join(temp_dir, f"clip_{idx:03d}")
    os.makedirs(clip_frames_dir, exist_ok=True)
    
    # Save each frame as a PNG
    for i, frame in enumerate(frames):
        frame_path = os.path.join(clip_frames_dir, f"frame_{i:04d}.png")
        cv2.imwrite(frame_path, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    
    # Use FFmpeg to create a video clip from these frames
    clip_video = os.path.join(temp_dir, f"clip_{idx:03d}.mp4")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", "60",
        "-i", os.path.join(clip_frames_dir, "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "60",
        "-t", f"{clip_duration:.3f}",
        clip_video
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"Created clip: {clip_video}")
    return clip_video

clip_videos = []
with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
    futures = {executor.submit(process_image, img, idx): idx for idx, img in enumerate(image_files)}
    for future in as_completed(futures):
        clip_video = future.result()
        if clip_video:
            clip_videos.append(clip_video)

if not clip_videos:
    raise ValueError("No clip videos were created.")

# 7️⃣ Concatenate all clip videos using FFmpeg concat demuxer
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
print("Concatenated clips into video:", temp_video)

# 8️⃣ Add audio to the concatenated video
temp_video_audio = os.path.join(temp_dir, "temp_video_with_audio.mp4")
ffmpeg_audio = [
    "ffmpeg", "-y",
    "-i", temp_video,
    "-i", audio_file,
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    temp_video_audio
]
subprocess.run(ffmpeg_audio, check=True)
print("Added audio to video:", temp_video_audio)

# 9️⃣ Generate an SRT subtitles file from your processed.txt
srt_file = "subtitles.srt"


def get_audio_duration(audio_file):
    """Get the duration of an audio file using FFmpeg."""
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        audio_file
    ]
    try:
        duration = float(subprocess.check_output(cmd).decode().strip())
        return duration
    except subprocess.CalledProcessError:
        print("Error: Failed to get audio duration")
        return 60.0  # Default to 60 seconds if duration detection fails

def is_section_header(text):
    """Check if the text is a short section header."""
    headers = ["Summary:", "Overall Assessment:", "Fake News Analysis:", "More Accurate Point of View:"]
    return text in headers

def generate_fixed_srt(text_file, audio_file, output_srt):
    """Generate SRT with fixed timing issues."""
    # Read subtitle text
    with open(text_file, "r", encoding="utf-8") as f:
        subtitles = [line.strip() for line in f if line.strip()]
    
    # Get total audio duration
    duration = get_audio_duration(audio_file)
    print(f"Audio duration: {duration:.2f} seconds")
    
    # Calculate subtitle timings with special handling for headers
    start_time = 1.0  # Start at 1 second
    subtitle_timings = []
    
    for text in subtitles:
        if is_section_header(text):
            # Section headers show for exactly 1 second
            end_time = start_time + 1.0
            subtitle_timings.append((start_time, end_time, text))
            start_time = end_time
        else:
            # Calculate duration based on text length and remaining time
            remaining_time = duration - start_time
            remaining_subtitles = sum(1 for t in subtitles[subtitles.index(text):] if not is_section_header(t))
            
            if remaining_subtitles > 0:
                # Allocate time proportionally to text length
                text_length = len(text.split())
                segment_duration = min(
                    max(3.0, text_length * 0.5),  # At least 3 seconds, more for longer text
                    remaining_time / remaining_subtitles  # Don't exceed average available time
                )
            else:
                # Last subtitle - use all remaining time
                segment_duration = remaining_time
            
            end_time = start_time + segment_duration
            subtitle_timings.append((start_time, end_time, text))
            start_time = end_time
    
    # Ensure last subtitle ends at audio duration
    if subtitle_timings and subtitle_timings[-1][1] < duration:
        last_start, _, last_text = subtitle_timings[-1]
        subtitle_timings[-1] = (last_start, duration, last_text)
    
    # Write SRT file
    write_srt_file(subtitle_timings, output_srt)
    
    return output_srt

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
    
    print(f"Generated fixed SRT subtitles: {output_file}")

# Generate fixed subtitles
generate_fixed_srt(subtitles_txt, audio_file, srt_file)

# 🔟 Burn subtitles into the video using FFmpeg
temp_video_subs = os.path.join(temp_dir, "temp_video_with_subs.mp4")
# Replace backslashes with forward slashes for FFmpeg
srt_ffmpeg = srt_file.replace("\\", "/")
ffmpeg_subs = [
    "ffmpeg", "-y",
    "-i", temp_video_audio,
    "-vf", f"subtitles='{srt_ffmpeg}'",
    "-c:a", "copy",
    temp_video_subs
]
subprocess.run(ffmpeg_subs, check=True)
print("Burned subtitles into video:", temp_video_subs)

# 1️⃣1️⃣ Load the last video from the Videos folder and stack vertically
# Find the video folder Minigames\output with the os library
current_dir = os.getcwd()
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
videos_folder = os.path.join(current_dir, "Minigames", "output")
videos = sorted(glob.glob(os.path.join(videos_folder, "*.avi")))
if not videos:
    raise FileNotFoundError("No video files found in the 'Videos' folder.")
last_video = videos[-1]
print("Using last video from Videos folder:", last_video)

# We'll use FFmpeg filter_complex to scale and stack videos vertically.
final_temp = os.path.join(temp_dir, "final_combined.mp4")
print("Stacking videos vertically...")
print("temp_video_subs:", temp_video_subs)
print("last_video:", last_video)
ffmpeg_stack = f'ffmpeg -y -i {temp_video_subs} -i {last_video} -filter_complex "[0:v]scale=1280:960[v0];[1:v]scale=1280:960[v1];[v0][v1]vstack=inputs=2[v]" -map "[v]" -map "0:a?" -c:v libx264 -c:a aac -b:a 192k -shortest {final_temp}'

subprocess.run(ffmpeg_stack, check=True)
print("Stacked videos vertically into:", final_temp)

# 1️⃣2️⃣ Move final combined video to the desired output location
print(f"Final video saved at: {final_temp}")
print(f"File size: {os.path.getsize(final_temp)} bytes")

# (Optional) Clean up temporary files
# import shutil
# shutil.rmtree(temp_dir)