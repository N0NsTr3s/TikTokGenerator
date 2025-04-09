import os
import glob
import cv2
import numpy as np
import moviepy.editor as mp
from moviepy.config import change_settings
import torch
import torchvision.transforms as transforms

# Set ImageMagick binary path if necessary
change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})

# Enforce CUDA usage; raise error if CUDA is not available
if not torch.cuda.is_available():
    raise EnvironmentError("CUDA is not available. Please run on a machine with CUDA enabled GPU.")
device = torch.device("cuda")
print(f"Using device: {device}")

# Function to apply zoom effect using PyTorch
def generate_zoom_frames(image, zoom_factor, num_frames):
    frames = []
    (h, w) = image.shape[:2]
    
    # Convert image to PyTorch tensor and send to GPU
    image_tensor = transforms.ToTensor()(image).unsqueeze(0).to(device)
    
    for i in range(num_frames):
        scale = 1 + (zoom_factor - 1) * (i / (num_frames - 1))
        new_w, new_h = int(w / scale), int(h / scale)
        
        # Calculate cropping box
        x1 = max((w - new_w) // 2, 0)
        y1 = max((h - new_h) // 2, 0)
        x2 = min((w + new_w) // 2, w)
        y2 = min((h + new_h) // 2, h)
        
        # Crop and resize using PyTorch operations on GPU
        cropped_image = image_tensor[:, :, y1:y2, x1:x2]
        zoomed_image = torch.nn.functional.interpolate(cropped_image, size=(h, w), mode='bilinear', align_corners=False)
        
        # Convert back to numpy array and append the frame
        frame = (zoomed_image.squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        frames.append(frame)
    
    return frames

# Load the images
image_files = sorted(glob.glob(r"D:\ComfyUI_windows_portable\ComfyUI\output\*ComfyUITikTok*.png"))
print(f"Found {len(image_files)} image files: {image_files}")

# Load voice over
voice_over = glob.glob(r"D:\ComfyUI_windows_portable\ComfyUI\output\audio\*.mp3")
if not voice_over:
    raise FileNotFoundError("No voice-over file found.")
audio_clip = mp.AudioFileClip(voice_over[0])

zoom = 1.5  # Adjust the zoom factor as needed
clips = []  # Initialize the clips list

# Calculate video duration
video_duration = audio_clip.duration + 1.5
print(f"Video duration: {video_duration}")
print(f"Number of images: {len(image_files)}")
clip_duration = video_duration / len(image_files) if len(image_files) > 0 else 0

# Process images and create zoomed frames
for image_file in image_files:
    if not os.path.isfile(image_file):
        print(f"Image file not found: {image_file}")
        continue
    
    try:
        print(f"Processing image: {image_file}")
        image = cv2.imread(image_file)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # Convert to RGB for PyTorch
        
        # Generate zoom frames
        num_frames = int(clip_duration * 30)  # Assuming 30 fps
        zoom_frames = generate_zoom_frames(image, zoom, num_frames)
        
        # Save zoomed frames as temporary image files
        frame_files = []
        for idx, frame in enumerate(zoom_frames):
            frame_file = image_file.replace(".png", f"_zoom_{idx}.png")
            cv2.imwrite(frame_file, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            frame_files.append(frame_file)
        
        # Create a video clip from the frames
        video_clip = mp.ImageSequenceClip(frame_files, fps=30)
        video_clip = video_clip.set_duration(clip_duration)
        clips.append(video_clip)
        print(f"Added clip, current number of clips: {len(clips)}")
    except Exception as e:
        print(f"Error processing image {image_file}: {str(e)}")

if not clips:
    raise ValueError("No clips were created. Check the image files and processing steps.")

print(f"Total number of clips: {len(clips)}")

# Concatenate clips
try:
    final_video = mp.concatenate_videoclips(clips, method="compose")
except Exception as e:
    raise ValueError(f"Error concatenating video clips: {str(e)}")

# Add voice over to the video
final_video = final_video.set_audio(audio_clip)

# Load the subtitles from the file
subtitles_file = r'D:\ComfyUI_windows_portable\ComfyUI\ComfyUI-to-Python-Extension\news.txt'
with open(subtitles_file, 'r') as file:
    subtitles = [subtitle.strip() for subtitle in file.readlines()]

# Calculate the time interval between each subtitle
interval = (video_duration - 2) / len(subtitles) if len(subtitles) > 0 else 0
final_clip = final_video

for i, subtitle in enumerate(subtitles):
    words = subtitle.split()
    
    # Split the subtitle into chunks of 4 words
    chunks = [" ".join(words[j:j+4]) for j in range(0, len(words), 4)]
    
    for k, chunk in enumerate(chunks):
        start_time = (i * interval) + (k * interval / len(chunks))
        end_time = start_time + (interval / len(chunks))
        
        subtitle_clip = (mp.TextClip(chunk, fontsize=60, color='white', stroke_color='black', stroke_width=2, font='Arial', method='caption')
                         .set_position((0.2, 0.2), relative=True)
                         .set_start(start_time)
                         .set_end(end_time))
        
        final_clip = mp.CompositeVideoClip([final_clip, subtitle_clip])

# Load the last video from the "Videos" folder
videos_folder = r'C:\Users\Edi\Videos'
video_files = sorted(glob.glob(os.path.join(videos_folder, '*.mp4')))
if not video_files:
    raise FileNotFoundError("No video files found in the 'Videos' folder.")
last_video = mp.VideoFileClip(video_files[-1])

# Resize the final video and the last video to the desired dimensions
final_clip = final_clip.resize(height=960)
last_video = last_video.resize(height=960)

# Stack the two videos vertically
combined_video = mp.CompositeVideoClip([final_clip.set_position(("center", "top")), last_video.set_position(("center", "bottom"))], size=(1080, 1920))

# Save the combined video
output_path = r'C:\Users\Edi\Desktop\testing py\ttk\final_video.mp4'
try:
    combined_video.write_videofile(
        filename=output_path,
        codec='h264_nvenc',  # Use NVIDIA encoder for GPU acceleration
        fps=30,
        audio_codec='aac',
        bitrate='6000k',
        audio_bitrate='192k',
        threads=8,
        preset='medium',
        verbose=True
    )
except Exception as e:
    raise ValueError(f"Error writing video file: {str(e)}")

if os.path.exists(output_path):
    print(f"Video created successfully: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")
else:
    print(f"Failed to create video: {output_path}")

# Delete files with the specified name
files_to_delete = glob.glob(r"D:\ComfyUI_windows_portable\ComfyUI\output\ComfyUITikTok*.png")
for file in files_to_delete:
    if os.path.exists(file):
        os.remove(file)
        print(f"File deleted: {file}")
    else:
        print(f"File not found: {file}")
