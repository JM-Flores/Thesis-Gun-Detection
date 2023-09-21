import cv2
import os
import json
import numpy as np
import copy
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from src import model
from src.body import Body
from src import util
import torch

# Initialize body estimation model
body_estimation = Body('model/body_pose_model.pth')

print(torch.cuda.is_available())
print(f"Torch device: {torch.cuda.get_device_name()}")

# Specify the folder containing the images/frames
image_folder = 'images/dataset/11'

# Get a list of image file names in the folder
image_files = [f for f in os.listdir(image_folder) if f.endswith('.jpg')]
image_files.sort()  # Sort the files to ensure the correct order

# Initialize a list to store the keypoints data
keypoints_data = []

# Function to load and process an image frame
def process_frame(frame_number):
    image_file = image_files[frame_number]
    print(f"Processing image: {image_file}")

    # Load the image
    test_image = os.path.join(image_folder, image_file)
    oriImg = cv2.imread(test_image)  # B,G,R order

    # Preprocessing:
    # Resize the image to a target size (e.g., 368x368 pixels)
    target_size = (368, 368)
    oriImg = cv2.resize(oriImg, target_size)

    # Body pose estimation
    candidate, subset = body_estimation(oriImg)

    # Visualize body pose on the image
    canvas = copy.deepcopy(oriImg)
    canvas = util.draw_bodypose(canvas, candidate, subset)

    # Extract keypoints data (coordinates and confidence scores)
    keypoints_info = {
        'frame_number': frame_number,
        'keypoints': []
    }

    for person_id in range(len(subset)):
        keypoints = {
            'person_id': person_id,
            'keypoints': []
        }
        for kp_id in range(18):  # 18 keypoints for body
            index = int(subset[person_id][kp_id])
            if not(index == -1): #if keypoint is detected, store coordiantes and confidence score
                x = int(candidate[index, 0])
                y = int(candidate[index, 1])
                confidence = candidate[index, 2]
                keypoints['keypoints'].append({
                    'x': x,
                    'y': y,
                    'confidence': confidence
                })
                # Draw keypoints on the image
                cv2.circle(canvas, (x, y), 3, (0, 0, 255), -1)  # Red circles for keypoints
            else: #else, put None coordinates and negative confidence score
                keypoints['keypoints'].append({
                    'x': None,
                    'y': None,
                    'confidence': -1
                })


        #Keypoints for hand region extraction
        left_wrist = keypoints['keypoints'][4]
        right_wrist = keypoints['keypoints'][7]
        left_elbow = keypoints['keypoints'][3]
        right_elbow = keypoints['keypoints'][6]
        
        def extract_hand_region(canvas, wrist, elbow):
           # Add bounding box of hand area based on wrist and elbow
            if elbow['confidence'] > 0 and wrist['confidence'] > 0:
                # approximate the position of the gun (center) by moving the wrist position further
                x_center = wrist['x'] + int((wrist['x'] - elbow['x']) * 0.35) 
                y_center = wrist['y'] + int((wrist['y'] - elbow['y']) * 0.35)
                # mark center of bounding box
                cv2.circle(canvas, (x_center, y_center), 3, (0, 0, 255), -1)

                radius = max(abs(x_center - elbow['x']),
                            abs(y_center - elbow['y']))
                x_min = x_center - radius
                y_min = y_center - radius
                x_max = x_center + radius
                y_max = y_center + radius
                cv2.rectangle(canvas, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2) 
        
        extract_hand_region(canvas, left_wrist, left_elbow)
        extract_hand_region(canvas, right_wrist, right_elbow)


        keypoints_info['keypoints'].append(keypoints)

    keypoints_data.append(keypoints_info)

    return canvas

# Create a function to update the animation
def update(frame):
    plt.clf()  # Clear the previous frame
    current_frame = process_frame(frame)
    plt.imshow(current_frame[:, :, [2, 1, 0]])  # Display the current frame
    plt.axis('off')
    plt.title(f'Frame {frame}')

# Create the animation
fig, ax = plt.subplots()
num_frames = len(image_files)
ani = FuncAnimation(fig, update, frames=num_frames, repeat=False)

# Display the animation
plt.show()

# Save the keypoints data to a JSON file
output_json_file = 'keypoints_data.json'
with open(output_json_file, 'w') as json_file:
    json.dump(keypoints_data, json_file, indent=4)

print(f"Keypoints data saved to {output_json_file}")
