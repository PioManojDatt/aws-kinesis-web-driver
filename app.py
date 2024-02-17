from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from engineio.payload import Payload
import cv2
from datetime import datetime
import os, base64
import socket
import requests
import numpy as np
from dotenv import load_dotenv
import threading
import json
load_dotenv('.env')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
ENGINEIO_MAX_DECODE_PACKETS = 500
# logger=True, engineio_logger=True, 
Payload.max_decode_packets = ENGINEIO_MAX_DECODE_PACKETS
socketio = SocketIO(app, logger=True, max_http_buffer_size=1000000000)

app.config['recording'] = False
app.config['recording_time'] = None

# Init frame variables
FIRST_FRAME = None
NEXT_FRAME = None
# Number of frames to pass before changing the frame to compare the current
# frame against
FRAMES_TO_PERSIST = 10
DELAY_COUNT = 0
# Minimum boxed area for a detected motion to count as actual motion
# Use to filter out noise or small objects
MIN_SIZE_FOR_MOVEMENT = 2000
MAX_RECORDING_TIME_SEC = 60 # 1 min
# sudo apt-get install libopenblas-dev
API_KEY = os.environ.get('FCM_KEY', '')

@app.route("/")
def index():
    # Render the index.html template
    return render_template("index.html")

    
def notify():
    frametime = datetime.now().strftime('%I:%M:%S')
    # Your api-key can be gotten from:  https://console.firebase.google.com/project/<project-name>/settings/cloudmessaging
    payload = {
        "title": "Motion Detected",
        "body": f"A new object or object motion has detected over the {socket.gethostname()} at {frametime}",
        "topic": socket.gethostname()
        }
    response = requests.post(os.getenv('NOTIFY_URL'), json.dumps(payload), headers={
        "device_id": socket.gethostname()
    })
    print(response.text)
    
def handle_motion_detection(image):
    global FIRST_FRAME, NEXT_FRAME, FRAMES_TO_PERSIST, MIN_SIZE_FOR_MOVEMENT, DELAY_COUNT
    # Set transient motion detected as false
    transient_movement_flag = False
    # Process the image as you wish
    # For example, apply a grayscale filter
    # Blur it to remove camera noise (reducing false positives)
    blur_image = cv2.GaussianBlur(image, (21, 21), 0)
    
    # If the first frame is nothing, initialise it
    if FIRST_FRAME is None: 
        FIRST_FRAME = blur_image 
    
    DELAY_COUNT += 1
    # Otherwise, set the first frame to compare as the previous frame
    # But only if the counter reaches the appriopriate value
    # The delay is to allow relatively slow motions to be counted as large
    # motions if they're spread out far enough
    if DELAY_COUNT > FRAMES_TO_PERSIST:
        DELAY_COUNT = 0
        FIRST_FRAME = NEXT_FRAME
    
    # Set the next frame to compare (the current frame)
    NEXT_FRAME = blur_image
    
    # Compare the two frames, find the difference
    frame_delta = cv2.absdiff(FIRST_FRAME, NEXT_FRAME)
    thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]

    # Fill in holes via dilate(), and find contours of the thesholds
    thresh = cv2.dilate(thresh, None, iterations = 2)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # loop over the contours
    for c in cnts:
        # If the contour is too small, ignore it, otherwise, there's transient movement
        if cv2.contourArea(c) > MIN_SIZE_FOR_MOVEMENT:
            transient_movement_flag = True
            break

    # The moment something moves momentarily, reset the persistent
    # movement timer.
    return transient_movement_flag
        
    
@socketio.on("video_data")
def video_data(data):
    # Convert the data to a numpy array
    image_data = data.split(',')[1]
    image_data = bytes(image_data, 'utf-8')
    np_data = np.frombuffer(base64.decodebytes(image_data), np.uint8)

    # Decode the data to an image
    image = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    detected = handle_motion_detection(image)
    if detected:
        if app.config['recording'] == False:
            app.config['recording_time'] = datetime.now()
            # Emit the start_record on no motion to the client
            thread = threading.Thread(target=notify)
            thread.start()
            print('Emit the start_record on motion to the client')
            emit("start_record")
            app.config['recording'] = True
        else:
            later = datetime.now()
            recording_time = (later - app.config['recording_time']).total_seconds()
            if recording_time > MAX_RECORDING_TIME_SEC:
                app.config['recording_time'] = datetime.now()
                print('Emit the stop_record on clip')
                emit("stop_record")
                
    elif app.config['recording_time']:
        later = datetime.now()
        recording_time = (later - app.config['recording_time']).total_seconds()
        if app.config['recording'] and recording_time > MAX_RECORDING_TIME_SEC:
            app.config['recording'] = False
            print('Emit the stop_record on no motion to the client')
            emit("stop_record")

@socketio.on("disconnect")
def disconnect():
    # Handle the client disconnect
    emit("stop_record", "")

@socketio.on_error_default
def default_error_handler(e):
    print(e) # "my error event"
    
if __name__ == "__main__":
    # Run the app
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)