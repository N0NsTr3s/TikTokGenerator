import os
import glob
import subprocess
import time

# Paths
image_dir = r"D:\ComfyUI_windows_portable\ComfyUI\output"
audio_dir = r"D:\ComfyUI_windows_portable\ComfyUI\output\audio"
subtitles_file = r"D:\ComfyUI_windows_portable\ComfyUI\ComfyUI-to-Python-Extension\processed.txt"
output_srt = r"subtitles.srt"
final_output = r"C:\Users\Edi\Desktop\testing py\ttk\final_video.mp4"

print("🚀 Processing video...")

# 1️⃣ Rename Images Sequentially
image_files = sorted(glob.glob(os.path.join(image_dir, "ComfyUITikTok_*.png")))
for index, file in enumerate(image_files):
    new_name = os.path.join(image_dir, f"frame{index:03d}.png")
    os.rename(file, new_name)

print(f"✅ Renamed {len(image_files)} images")

# 2️⃣ Create Video from Images
subprocess.run([
    "ffmpeg", "-framerate", "30", "-i", os.path.join(image_dir, "frame%03d.png"),
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
    "temp_video.mp4"
])
print("✅ Created video from images")

# 3️⃣ Find Audio File
audio_files = glob.glob(os.path.join(audio_dir, "comfyUIVoiceTTK_*_en-US-SteffanNeural.mp3"))
if not audio_files:
    raise FileNotFoundError("No audio file found!")
audio_file = audio_files[0]

print(f"✅ Found audio file: {audio_file}")

# 4️⃣ Add Audio
subprocess.run([
    "ffmpeg", "-i", "temp_video.mp4", "-i", audio_file, "-c:v", "copy", "-c:a", "aac", "temp_video_with_audio.mp4"
])
print("✅ Added audio to video")

# 5️⃣ Convert Subtitles to SRT
with open(subtitles_file, 'r', encoding='utf-8') as file:
    subtitles = [line.strip() for line in file.readlines() if line.strip()]

print(f"✅ Loaded {len(subtitles)} subtitles")

# Calculate the actual length of the video
result = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

audio_duration = float(result.stdout.strip())
interval = audio_duration / len(subtitles) if subtitles else 1

print(f"✅ Calculated interval: {interval:.3f} seconds")
with open(output_srt, "w", encoding="utf-8") as f:
    for i, subtitle in enumerate(subtitles):
        start_time = time.strftime('%H:%M:%S', time.gmtime(i * interval)) + f",{int((i * interval % 1) * 1000):03d}"
        end_time = time.strftime('%H:%M:%S', time.gmtime((i + 1) * interval)) + f",{int(((i + 1) * interval % 1) * 1000):03d}"

        f.write(f"{i+1}\n{start_time} --> {end_time}\n{subtitle}\n\n")

print(f"✅ Converted subtitles to SRT: {output_srt}")

# 6️⃣ Burn Subtitles
try:
    subprocess.run([
        "ffmpeg", "-i", "temp_video_with_audio.mp4", "-vf", f"subtitles={output_srt}",
        "-c:a", "copy", final_output
    ])
except Exception as e:
    raise ValueError(f"Error writing video file: {str(e)}")

print(f"✅ Final video saved at: {final_output}")
print(f"File size: {os.path.getsize(final_output)} bytes")