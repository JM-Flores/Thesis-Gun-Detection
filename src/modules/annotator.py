import csv
import os
import xml.etree.ElementTree as ET
import torch
import numpy as np
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

# return true if at least one of the hand regions have gun
# gun box is the annotation from the dataset
# hand_regions is [left_hand, right_hand]
# each box is [x_min,y_min,x_max,y_max]
def hand_regions_have_gun(hand_regions, gun_box):
    print("hand_regions: ", hand_regions)
    print("gun_box: ", gun_box)

    # if at least one hand region have a gun, return true
    for hand_region in hand_regions:
        if _hand_region_have_gun(hand_region, gun_box):
            print("Label: True, Hand regions have gun!")
            return True
    print("Label: False, Hand regions don't have guns")
    return False

# return true if handregion have gun
# gun box is the annotation from the dataset
# box is [x_min,y_min,x_max,y_max]
def _hand_region_have_gun(hand_box, gun_box):
    print("Comparing the boxes: ")
    print("\thand_box: ", hand_box)
    print("\tgun_box: ", gun_box)
    have_gun = False

    if hand_box is None or gun_box is None:
        return False

    intersect_threshold = 0.4
	
    # determine the (x, y)-coordinates of the intersection rectangle
    xA = max(hand_box[0], gun_box[0])
    yA = max(hand_box[1], gun_box[1])
    xB = min(hand_box[2], gun_box[2])
    yB = min(hand_box[3], gun_box[3])
	# compute the area of intersection rectangle
    inter_area = max(0, xB - xA + 1) * max(0, yB - yA + 1)

    # compute are of gun box
    gun_area = (gun_box[2] - gun_box[0] + 1) * (gun_box[3] - gun_box[1] + 1)

    # intersection area over gun box area
    inter_over_gun = inter_area / gun_area

    if inter_over_gun > intersect_threshold:
        have_gun = True

    return have_gun

# # return person label list = [person 0, person 1,...,person N] Ex. [False, True]
# # gun box is [x_min,y_min,x_max,y_max]
# def annotate_frame(frame_image, gun_box, confidence_min = 0.1):
#     # Initialize body estimation model
#     body_estimation = Body('model/body_pose_model.pth')

#     # Body pose estimation
#     candidate, subset = body_estimation(frame_image)

#     # List of person labels
#     persons_label = []

#     for person_id in range(len(subset)):
#         print("Person ID: ", person_id)

#         # extract keypoints dictionary (person_id,keypoints)
#         keypoints = bodykeypoints.extract_keypoints(person_id, candidate, subset, confidence_min)

#         # get box coordinates of hand regions
#         hand_intersect_threshold = 0.9
#         hand_regions = handregion.extract_hand_regions(keypoints, hand_intersect_threshold)

#         print("extracted hand_regions: ", hand_regions)

#         # check intersection of hand_regions and gun_box
#         have_gun = hand_regions_have_gun(hand_regions, gun_box)

#         label = True if have_gun else False
#         persons_label.append(label)

#     return persons_label

# return person label list = [person 0, person 1,...,person N] Ex. [False, True]
# gun box is [x_min,y_min,x_max,y_max]
def annotate_frame(hand_regions_in_frame, gun_boxes, num_of_person):

    # List of person labels
    persons_labels = []

    for person_id in range(num_of_person):
        print("Person ID: ", person_id)

        person_label = False
        for gun_box in gun_boxes:
            # check intersection of hand_regions and gun_box
            have_gun = hand_regions_have_gun(hand_regions_in_frame[person_id], gun_box)

            label = True if have_gun else False

            if label:
                person_label = True
                break
        persons_labels.append(person_label)

    print("persons label: " , persons_labels)
    return persons_labels

# return the gun box [x_min,y_min,x_max,y_max] from the annotations
# return None if annotation file does not exist
def get_gunboxes(image_filename, annotation_folder):
    # base_name, _ = os.path.splitext(image_filename)
    annotation_file = annotation_folder + image_filename + ".xml"

    bndboxes = []
    
    # Parse the XML file
    tree = ET.parse(annotation_file)
    root = tree.getroot()

    # Iterate through all <object> elements
    for obj in root.findall('.//object'):
        name = obj.find('name')
        
        # Check if the object's name is "pistol"
        if name is not None and name.text == 'pistol':
            bndbox = obj.find('bndbox')
            
            if bndbox is not None:
                # Extract the coordinates and store them as [x_min, y_min, x_max, y_max]
                x_min = int(bndbox.find('xmin').text)
                y_min = int(bndbox.find('ymin').text)
                x_max = int(bndbox.find('xmax').text)
                y_max = int(bndbox.find('ymax').text)
                
                bndboxes.append([x_min, y_min, x_max, y_max])

    return bndboxes

# reads the hand_regions_coords.txt generated by the data generator
# returns the list version of the text
# [frame 0 = [person 0 = [hand_regions = [hand_region = [x_min,..., y_max] , ], ], ] , ]
def read_hand_regions_txt(file_path):
    try:
        with open(file_path, 'r') as text_file:
            data = text_file.read()
            nested_list = eval(data)
            if isinstance(nested_list, list):
                return nested_list
            else:
                raise ValueError("The file does not contain a valid nested list.")
    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# gun box list is the gun box coordinates per frame 
# each row is [x_min,y_min,x_max,y_max]
def create_vid_annotation(dataset_folder, data_folder, video_name, output_folder, annotation_folder):
    # Path of dataset video folder
    dataset_video_folder = dataset_folder + video_name + "/"

    # Path of data video folder
    data_video_folder = data_folder + video_name + "/"

    # Path of output folder
    output_folder = output_folder + video_name + "/"

    
    hand_regions_txt = data_video_folder + "hand_regions_coords.txt"

    if not os.path.exists(hand_regions_txt):
        return None

    # Get hand_regions element: hand_regions_of_vid[frame_num][person_id]
    hand_regions_of_vid = read_hand_regions_txt(hand_regions_txt)

    num_of_frames = len(hand_regions_of_vid)


    # Get a list of image file names in the dataset video folder
    image_files = [f for f in os.listdir(dataset_video_folder) if f.endswith('.jpg')]
    image_files.sort()  # Sort the files to ensure the correct order

    # Initialize list of persons label per frame
    video_labels = []

    for frame_num in range(num_of_frames):
        print("")
        print("FRAME NUM: ", frame_num)
        hand_regions_in_frame = hand_regions_of_vid[frame_num]

        num_of_person = len(hand_regions_of_vid[frame_num])

        # Get the file name of the image
        base_name = os.path.basename(image_files[frame_num])
        frame_filename, _ = os.path.splitext(base_name)

        gun_boxes = get_gunboxes(frame_filename, annotation_folder)

        persons_label = annotate_frame(hand_regions_in_frame, gun_boxes, num_of_person)
        
        video_labels.append(persons_label)

    return video_labels

def save_video_labels_csv(video_labels, output_folder):
    file_path = output_folder + "video_labels.csv"
    with open(file_path, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)

        # write header
        max_persons = max(len(sublist) for sublist in video_labels)
        csv_row = ["frame num"] + [f"person {i}" for i in range(max_persons)]
        csv_writer.writerow(csv_row)
        
        # write labels
        for frame_num in range(len(video_labels)):
            csv_row = [f"frame {frame_num}"] + [int(person_label) for person_label in video_labels[frame_num]]
            csv_writer.writerow(csv_row)
    print("Video labels stored in :" , file_path)




