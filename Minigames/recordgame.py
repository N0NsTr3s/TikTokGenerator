import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
import sys
import datetime
import time
import os

# define the codec
fourcc = cv2.VideoWriter_fourcc(*"XVID")
fps = 28.0  # Set the desired frame rate

# search for the window, getting the first matched window with the title
window_titles = ["Racing Game", "Rotating Circles Game"]
windows = []
for title in window_titles:
    windows = gw.getWindowsWithTitle(title)
    if windows:
        print(f"Window found: {title}")
        break
if not windows:
    print("Window not found!")
    sys.exit()

w = windows[0]
w.activate()

# create the output directory if it doesn't exist
output_dir = os.path.join(os.path.dirname(__file__), "output")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# create the video write object
current_time = datetime.datetime.now().strftime("%d-%m-%y-%H-%M-%S")
out = cv2.VideoWriter(f"{output_dir}/output-{current_time}.avi", fourcc, fps, (w.width-50, w.height-50))

# Create a minimal window to display the frames next to the racing game window
cv2.namedWindow("screenshot", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("screenshot", cv2.WND_PROP_TOPMOST, 1)
cv2.resizeWindow("screenshot", 200, 150)
cv2.moveWindow("screenshot", w.left + w.width + 10, w.top)

# Calculate the interval between frames
frame_interval = 1.0 / fps

while True:
    start_time = time.time()

    # check if the window still exists
    if not any(win.title in ["Racing Game", "Rotating Circles Game"] for win in gw.getAllWindows()):
        break

    # make sure the window is active
    w.activate()
    # make a screenshot
    img = pyautogui.screenshot(region=(w.left+25, w.top+30, w.width-50, w.height-50))
    # convert these pixels to a proper numpy array to work with OpenCV
    frame = np.array(img)
    # convert colors from RGB to BGR (OpenCV uses BGR by default)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    # write the frame
    out.write(frame)
    # show the frame
    cv2.imshow("screenshot", frame)
    # if the user clicks q, it exits
    if cv2.waitKey(1) == ord("q"):
        break

    # Wait for the next frame
    elapsed_time = time.time() - start_time
    time_to_wait = frame_interval - elapsed_time
    if time_to_wait > 0:
        time.sleep(time_to_wait)

# make sure everything is closed when exited
cv2.destroyAllWindows()
out.release()