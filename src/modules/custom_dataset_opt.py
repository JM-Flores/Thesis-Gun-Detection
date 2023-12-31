import os
import torch
from torch.utils.data import Dataset
from torchvision import transforms
import torchvision
import pandas as pd
import csv
import numpy as np
from src.modules import data_creator, motion_analysis
import cv2
import random

# Set a random seed for reproducibility
torch.manual_seed(12)
torch.cuda.manual_seed(12)
np.random.seed(12)
random.seed(12)
os.environ['PYTHONHASHSEED'] = str(12)
torch.cuda.manual_seed_all(12)
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.enabled = False

torch.backends.cudnn.deterministic=True

class CustomGunDataset_opt(Dataset):
    
    def __init__(self, root_dir, window_size = 3, transform=None, video=None, showLog=False):
        self.data_dir = root_dir
        self.window_size = window_size
        self.data = []  # A list to store data entries
        self.transform = transform
        self.video = video
        
        video_names = []
        if self.video is None:
            video_names = _list_subfolders(root_dir)
        else:
            video_names.append(str(video))
        if showLog:
            print("video list detected by CustomGunDataset: ", video_names)

        # Load data entries based on the directory structure
        for index, video_name in enumerate(video_names):
            video_dir = os.path.join(root_dir, str(video_name))
            annotation_path = os.path.join(video_dir, 'video_labels.csv')
            
            if os.path.exists(video_dir):
                # Get num of frames and persons from the video labels csv file
                num_frames, num_person = data_creator.get_num_frames_person(self.data_dir, video_name)

                for person_id in range(num_person):  # Iterate through subdirectories
                    person_name = 'person_' + str(person_id)
                    vidx_keypoints = {}  # Initialize vidx_keypoints for each subdir
                    framex_keypoints = {}

                    person_folder_path = os.path.join(video_dir, person_name)
                    hand_folder_path = os.path.join(person_folder_path, "hand_image")
                    pose_folder_path = os.path.join(person_folder_path, "binary_pose")
                    motion_folder_path = os.path.join(person_folder_path, "motion_keypoints")

                    # Check if all required directories exist
                    if not os.path.exists(hand_folder_path) or not os.path.exists(pose_folder_path) or not os.path.exists(motion_folder_path):
                        if showLog:
                            print(f"Skipping subdir {person_name}: Required directories missing.")
                        continue  # Skip to the next subdir
                    
                    else:
                        # # Load data entries
                        # imgs_hand = [img for img in os.listdir(hand_folder_path) if img.endswith(".png")]
                        # imgs_pose = [img for img in os.listdir(pose_folder_path) if img.endswith(".png")]
                        # data_names = []
                    
                        
                        for frame_num in range(num_frames):
                            if not showLog:
                                print(f'Loading Dataset...[{index}/{len(video_names)}][{person_id}/{num_person}][{frame_num}/{num_frames}]      ', end='\r')
                            hand_path = os.path.join(hand_folder_path, 'hands_' + str(frame_num) + '.pt')
                            pose_path = os.path.join(pose_folder_path, 'pose_' + str(frame_num) + '.png')
                            motion_path = os.path.join(motion_folder_path, "keypoints_seq.txt")
                            
                            # GUN DATA
                            hand_file_exist = os.path.isfile(hand_path)
                            gun_data = None

                            if hand_file_exist:
                                hand_tensor = torch.load(hand_path)

                                gun_data = hand_tensor
                            
                            # POSE DATA
                            pose_file_exist = os.path.isfile(pose_path)
                            pose_data = None

                            if pose_file_exist:
                                preprocess = transforms.Compose([ transforms.ToTensor() ])
                                image = cv2.imread(pose_path, cv2.IMREAD_GRAYSCALE)
                                input_image = preprocess(image)
                                # input_image = input_image.unsqueeze(0)
                                pose_data = input_image


                            # MOTION DATA

                            motion_data = motion_analysis.get_one_sequence(motion_path, frame_num, self.window_size)

                            # LABEL
                            # Read the CSV file
                            data_label = None
                            with open(annotation_path, 'r') as csvfile:
                                csv_reader = csv.reader(csvfile)
                                header = next(csv_reader) 
                                
                                if person_id < num_person:
                                    column_index = person_id + 1
                                    row_index = frame_num

                                    # Iterate through the CSV rows
                                    for i, row in enumerate(csv_reader):
                                        if i == row_index:
                                            if len(row) > column_index:
                                                data_label = row[column_index]
                                                # Check if the value is empty or missing, and set it to "null" if so
                                                if not data_label:
                                                    data_label = None
                                elif showLog:
                                    print(f"No match found in CSV file for {person_name}")

                            
                            sample_name = f"Vid{video_name}_{person_name}_Frame{frame_num}"
                                
                            
                            gun_data_exist = gun_data is not None
                            pose_data_exist = pose_data is not None
                            motion_data_exist = motion_data is not None

                                
                            if gun_data_exist and pose_data_exist and motion_data_exist:
                                data_entry = {
                                    "data_name": sample_name,
                                    "gun_data": gun_data,
                                    "pose_data": pose_data,
                                    "motion_data": motion_data,
                                    "label": data_label
                                }
                                self.data.append(data_entry)
                            else:
                                if showLog:
                                    print(f"Skipping {sample_name}:")
                                    print("\tGun data exist: ", gun_data_exist)
                                    print("\tPose data exist: ", pose_data_exist)
                                    print("\tMotion data exist: ", motion_data_exist)
                                continue  # Continue to the next image
                
        if not showLog:
            print(f'Loading Dataset...[{len(video_names)}/{len(video_names)}]                            ')

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        data_entry = self.data[index]
        data_name = self.data[index].get("data_name")
        gun_data = self.data[index].get("gun_data")
        pose_data = self.data[index].get("pose_data")
        motion_data = self.data[index].get("motion_data")
        label = self.data[index].get("label")

        label = int(label)
        label = torch.tensor(label, dtype=torch.long)

        return data_name, gun_data, pose_data, motion_data, label

def _list_subfolders(main_folder_path):
    subfolders = []

    # Custom sorting key function
    def custom_sort_key(item):
        # Split the string into parts using underscores
        parts = item.split('_')
        if len(parts) == 3:
            # For numeric strings, return a tuple (0, int) to sort them first
            return (1, int(parts[2]))
        else:
            # For alphanumeric strings, return a tuple (1, int) to sort them after the numeric ones
            return (0, int(parts[-1]))
    
    # Check if the main folder path exists
    if os.path.exists(main_folder_path) and os.path.isdir(main_folder_path):
        for folder_name in os.listdir(main_folder_path):
            folder_path = os.path.join(main_folder_path, folder_name)
            if os.path.isdir(folder_path):
                subfolders.append(folder_name)
    
    return sorted(subfolders, key=custom_sort_key)



