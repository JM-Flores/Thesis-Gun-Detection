import pandas as pd
import torch
import os
from src.modules import motion_analysis
from yolo.pytorchyolo import models
import torchvision.transforms as transforms
from src.modules.posecnn import poseCNN
from src.modules.gun_yolo import CustomDarknet53, GunLSTM, GunLSTM_Optimized, Gun_Optimized
from src.modules.combined_model import GPM1, GPM2
from src.modules.custom_dataset import CustomGunDataset
from src.modules.custom_dataset_gunLSTM import CustomGunLSTMDataset
from src.modules.custom_dataset_gunLSTM_opt import CustomGunLSTMDataset_opt
from src.modules.custom_dataset_opt import CustomGunDataset_opt
from src.modules.train import train_model
from src.modules.cross_validate import cross_validate
from torch.utils.data import DataLoader, Subset
import torch.optim as optim
from sklearn.model_selection import train_test_split, KFold
import matplotlib.pyplot as plt
import seaborn as sns
from holocron.models import darknet53
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

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
print("Device: " , device)


# Load the models
darknet_model = darknet53(pretrained=True)
pose_model = poseCNN()

hidden_size = 100
window_size = 5
lstm_layers = 1
batch_size = 16
learning_rate = 1e-5
num_epochs = 60

user_input =  0
model_name = ''
while True:
    user_input = input("Do you want to train GPM (1), GP (2), GPM2 (3), GPM2-opt (4), GP-opt (5), GPM-opt (6)? Enter '1', '2', '3', '4', '5', '6': ").strip().upper()
    if user_input == '1':
        gun_model = CustomDarknet53(darknet_model)
        motion_model = motion_analysis.MotionLSTM(hidden_size, lstm_layers)
        combined_feature_size = 20 + 20 + hidden_size #total num of features of 3 model outputs
        model_name = 'GPM'
        break
    elif user_input == '2':
        gun_model = CustomDarknet53(darknet_model)
        combined_feature_size = 20 + 20 #total num of features of 3 model outputs
        model_name = 'GP'
        break
    elif user_input == '3':
        gun_model = GunLSTM(darknet_model, hidden_size=hidden_size)
        combined_feature_size = 20 + hidden_size #total num of features of 3 model outputs
        model_name = 'GPM2'
        break
    elif user_input == '4':
        gun_model = GunLSTM_Optimized(hidden_size, lstm_layers)
        combined_feature_size = 20 + hidden_size #total num of features of 3 model outputs
        model_name = 'GPM2-opt'
        break
    elif user_input == '5':
        gun_model = Gun_Optimized()
        combined_feature_size = 20 + 20 #total num of features of 3 model outputs
        model_name = 'GP-opt'
        break
    elif user_input == '6':
        gun_model = Gun_Optimized()
        motion_model = motion_analysis.MotionLSTM(hidden_size, lstm_layers)
        combined_feature_size = 20 + 20 + hidden_size #total num of features of 3 model outputs
        model_name = 'GPM-opt'
        break
    else:
        print("Invalid input. Please enter '1' for all three models or '2' for combined model with no motion or '3' for new motion model.")

root_dir = 'data'
if user_input == '3': 
    # DATASET FOR NEW MODEL
    custom_dataset = CustomGunLSTMDataset(root_dir=root_dir, window_size = window_size)
elif user_input == '4': 
    # DATASET FOR NEW MODEL optimized
    custom_dataset = CustomGunLSTMDataset_opt(root_dir=root_dir, window_size = window_size)
elif user_input == '5' or user_input == '6': 
    # DATASET FOR old model optimized
    custom_dataset = CustomGunDataset_opt(root_dir=root_dir, window_size = window_size)
else:    
    custom_dataset = CustomGunDataset(root_dir=root_dir, window_size = window_size)

print ("Number of samples in dataset: ", len(custom_dataset))

label_0 = 0
label_1 = 0

for idx, data_entry in enumerate(custom_dataset.data):
    label = data_entry["label"]
    if label == '0':
        label_0+=1
    elif label == '1':
        label_1+=1

print ("Number of label 0: ", label_0)
print ("Number of label 1: ", label_1)

# Set the device
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

excel_filename = 'logs/results.xlsx'

train_loss = []
val_loss = []
folds = 5
kf = KFold(n_splits=folds, random_state=42, shuffle=True)
for fold_num, (train_indices, val_indices) in enumerate(kf.split(custom_dataset)):

    # (Re)Initialize model
    if user_input == '1':
        combined_model = GPM1(gun_model, pose_model, motion_model, combined_feature_size)
    elif user_input == '2':
        combined_model = GP(gun_model, pose_model, combined_feature_size)
    elif user_input == '3':
        combined_model = GPM2(gun_model, pose_model, combined_feature_size)
    elif user_input == '4':
        combined_model = GPM2(gun_model, pose_model, combined_feature_size)
    elif user_input == '5':
        combined_model = GPM2(gun_model, pose_model, combined_feature_size)
    elif user_input == '6':
        combined_model = GPM1(gun_model, pose_model, motion_model, combined_feature_size)

    combined_model.to(device)
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = optim.Adam(combined_model.parameters(), lr=learning_rate)

    train_dataset = Subset(dataset=custom_dataset, indices=train_indices)
    val_dataset = Subset(dataset=custom_dataset, indices=val_indices)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # Print Model Info
    print("\n")
    model_info = {
        'fold'          : fold_num+1,
        'model_type'    : model_name,
        'window_size'   : window_size,
        'hidden_size'   : hidden_size,
        'lstm_layers'   : lstm_layers,
        'train_set_size': len(train_dataset),
        'val_set_size'  : len(val_dataset),
        'batch_size'    : batch_size,
        'criterion'     : criterion.__class__.__name__,
        'optimizer'     : optimizer.__class__.__name__,
        'learning_rate' : optimizer.param_groups[0]['lr'],
        'epochs'        : num_epochs
    }
    df = pd.DataFrame([model_info]).T.rename(columns={0: 'Value'})
    df = df.reset_index().rename(columns={'index': 'Hyperparameter'})
    print(f'\n{df.to_string(index=False)}\n')

    run_number, trained_model, train_losses, val_losses = cross_validate(
        user_input, 
        train_loader, 
        val_loader, 
        combined_model, 
        criterion, 
        optimizer, 
        device, 
        num_epochs, 
        excel_filename,
        fold_num,
        save=True,
        model_info=model_info,
        save_excel=fold_num+1==folds
    )
    train_loss.append(train_losses)
    val_loss.append(val_losses)

    # Look into incorrect predictions
    incorrect_predictions = []
    video_loader = DataLoader(val_dataset)
    trained_model.eval()
    with torch.no_grad():
        for video in video_loader:
            data_name, gun_data, pose_data, motion_data, target_label = video

            gun_data = gun_data.to(device)
            pose_data = pose_data.to(device)
            motion_data = motion_data.to(device)
            target_label = target_label.to(device)
            
            if user_input == '1' or user_input == '6':
                combined_output = trained_model(gun_data, pose_data, motion_data)
            else:
                combined_output = trained_model(gun_data, pose_data)
            
            predicted_label = torch.argmax(combined_output)
            if predicted_label != target_label:
                incorrect_predictions.append({'data_name': data_name[0], 'predicted_label': predicted_label, 'target_label': target_label})

    # Save Incorrect Predictions
    incorrect_predictions_path = f'logs/run#{run_number}/fold{fold_num+1}/IncorrectPredictions.txt'
    with open(incorrect_predictions_path, 'w') as file:
        for item in incorrect_predictions:
            file.write(item['data_name'] + ':\n')
            file.write(f'  Predicted Label: {item["predicted_label"]}\n')
            file.write(f'  Correct Label: {item["target_label"]}\n\n')
        print(f'Incorrect Predictions saved to: {incorrect_predictions_path}')
