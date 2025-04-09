import subprocess

scripts = ["newscrawler.py", "MTTS_api.py", "tiktokimggen.py", "editvideo.py", "post.py"]

for script in scripts:
    subprocess.run(["python", script])