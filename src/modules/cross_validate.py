import torch
import torch.optim as optim
import torch.nn as nn
from torch.utils.data import DataLoader
import time
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import pandas as pd
import os
from datetime import datetime
import numpy as np
import random
import matplotlib.pyplot as plt

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

def plot_confusion_matrix(matrix, classes, title, path):
    """
    Plot and save the confusion matrix as an image.
    """
    plt.figure(figsize=(len(classes) + 2, len(classes) + 2))
    plt.imshow(matrix, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title(title, fontsize=14)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45, fontsize=12)
    plt.yticks(tick_marks, classes, fontsize=12)

    fmt = 'd'
    thresh = matrix.max() / 2.
    for i, j in itertools.product(range(matrix.shape[0]), range(matrix.shape[1])):
        plt.text(j, i, format(matrix[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if matrix[i, j] > thresh else "black",
                 fontsize=10)

    plt.ylabel('True label', fontsize=14)
    plt.xlabel('Predicted label', fontsize=14)
    plt.tight_layout()

    plt.savefig(path)
    plt.close()

def cross_validate( user_input, 
                    train_loader, 
                    val_loader, 
                    combined_model, 
                    criterion, 
                    optimizer, 
                    device, 
                    num_epochs, 
                    excel_filename, 
                    fold_num=None, 
                    save=False, 
                    model_info=None,
                    save_excel=False):

    train_losses = []  # To store training losses for each epoch
    val_losses = []    # To store validation losses for each epoch
    train_accuracies = []
    val_accuracies = []
    outputs = []       # To store per epoch data

    # Get the current date and time
    current_datetime = datetime.now().strftime('%Y-%m-d %H:%M:%S')

    # Get model name
    model_name = ''
    if user_input == '1':
        model_name = 'GPM'
    elif user_input == '2':
        model_name = 'GP'
    elif user_input == '3':
        model_name = 'GPM2'
    elif user_input == '4':
        model_name = 'GPM2-opt'
    elif user_input == '5':
        model_name = 'GP-opt'
    elif user_input == '6':
        model_name = 'GPM-opt'


    # Get the run number based on the existing Excel file
    run_number = 1
    if os.path.exists(excel_filename):
        existing_df = pd.read_excel(excel_filename)
        run_number = len(existing_df) + 1

    log_folder = f'logs/run#{run_number}/fold{fold_num+1}/'

    # Create The Logs Folder
    if not os.path.exists(log_folder): 
        os.makedirs(log_folder)

    print("Training Started: \n")

    for epoch in range(num_epochs):
        start_time = time.time()
        combined_model.train()
        total_train_loss = 0
        correct = 0
        total = 0
        train_predictions = []
        train_targets = []
        numBatches = len(train_loader)
        for index, batch in enumerate(train_loader):
            data_name, gun_data, pose_data, motion_data, target_labels = batch

            print(f'Epoch [{epoch+1}/{num_epochs}] {index}/{numBatches}', end='\r')

            gun_data = gun_data.to(device)
            pose_data = pose_data.to(device)
            motion_data = motion_data.to(device)
            target_labels = target_labels.to(device)

            optimizer.zero_grad()

            if user_input == '1' or user_input == '6':
                combined_output = combined_model(gun_data, pose_data, motion_data)
            else:
                combined_output = combined_model(gun_data, pose_data)

            _, predicted = torch.max(combined_output, 1)  # Get the class with the highest probability
            total += target_labels.size(0)  # Accumulate the total number of examples
            correct += (predicted == target_labels).sum().item()  # Count correct predictions

            loss = criterion(combined_output, target_labels)
            loss.backward()

            # nn.utils.clip_grad_norm_(combined_model.parameters(), max_norm=2)

            optimizer.step()

            total_train_loss += loss.item()
            train_predictions.extend(predicted.cpu().numpy())
            train_targets.extend(target_labels.cpu().numpy())

        print(f'Epoch [{epoch+1}/{num_epochs}] {numBatches}/{numBatches}', end='\r')
        train_accuracy = 100 * correct / total
        train_precision = precision_score(train_targets, train_predictions, average='weighted')
        train_recall = recall_score(train_targets, train_predictions, average='weighted')
        train_f1_score = f1_score(train_targets, train_predictions, average='weighted')
        train_confusion_matrix = confusion_matrix(train_targets, train_predictions)

        average_train_loss = total_train_loss / len(train_loader)
        train_losses.append(average_train_loss)
        train_accuracies.append(train_accuracy)

        # Validation loop
        combined_model.eval()  # Set the model to evaluation mode
        total_val_loss = 0
        correct = 0
        total = 0
        val_predictions = []
        val_targets = []

        with torch.no_grad():
            for batch in val_loader:
                data_name, gun_data, pose_data, motion_data, target_labels = batch

                gun_data = gun_data.to(device)
                pose_data = pose_data.to(device)
                motion_data = motion_data.to(device)
                target_labels = target_labels.to(device)
                
                if user_input == '1' or user_input == '6':
                    combined_output = combined_model(gun_data, pose_data, motion_data)
                else:
                    combined_output = combined_model(gun_data, pose_data)
                
                _, predicted = torch.max(combined_output, 1)  # Get the class with the highest probability
                total += target_labels.size(0)  # Accumulate the total number of examples
                correct += (predicted == target_labels).sum().item()  # Count correct predictions

                val_loss = criterion(combined_output, target_labels)
                total_val_loss += val_loss.item()
                val_predictions.extend(predicted.cpu().numpy())
                val_targets.extend(target_labels.cpu().numpy())

        val_accuracy = 100 * correct / total
        val_precision = precision_score(val_targets, val_predictions, average='weighted')
        val_recall = recall_score(val_targets, val_predictions, average='weighted')
        val_f1_score = f1_score(val_targets, val_predictions, average='weighted')
        val_confusion_matrix = confusion_matrix(val_targets, val_predictions)

        end_time = time.time()  # Record the end time for the epoch
        epoch_time = end_time - start_time  # Calculate the time taken for the epoch
        
        average_val_loss = total_val_loss / len(val_loader)
        val_losses.append(average_val_loss)
        val_accuracies.append(val_accuracy)

        combined_model.train()  # Set the model back to training mode

        output =  "Epoch [{}/{}], Training Accuracy: {:.2f}%, Training Loss: {:.4f}, Validation Accuracy: {:.2f}%, Validation Loss: {:.4f}, Time: {:.2f} seconds\n".format(epoch + 1, num_epochs, train_accuracy, average_train_loss, val_accuracy, average_val_loss, epoch_time)
        output += "Training Precision: {:.4f}, Training Recall: {:.4f}, Training F1 Score: {:.4f}\n".format(train_precision, train_recall, train_f1_score)
        output += "Validation Precision: {:.4f}, Validation Recall: {:.4f}, Validation F1 Score: {:.4f}\n".format(val_precision, val_recall, val_f1_score)
        print(output + '\n', end='\r')

        outputs.append(output) # collect outputs

    # Save Model Last Epoch
    if save:
        model_checkpoint = {
            'epoch': epoch,
            'model_state_dict': combined_model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'loss': loss
        }
        if model_info is not None:
            model_checkpoint['model_info'] = model_info
        model_folder = f'{log_folder}model/'
        if not os.path.exists(model_folder):
            os.makedirs(model_folder)
        model_path = f'{model_folder}model_epoch_{epoch}.pt'
        torch.save(model_checkpoint, model_path)
        print(f'model saved in: {model_path}')

    # Save per Epoch data
    output_log_path = f'{log_folder}run#{run_number}_OutputLog.txt'
    with open(output_log_path, 'w') as file:
        model_architecture = '\t' + (str(combined_model)).replace("\n", "\n\t")
        file.write(f'Model Architecture:\n{model_architecture}\n')
        if model_info is not None:
            file.write('\nHyperparameters:\n')
            for key, value in model_info.items():
                file.write(f'\t{key}\t: {value}\n')
        file.write('Per Epoch Output:\n')
        for output in outputs:
            file.write('\t' + output.replace('\n', '\n\t') + '\n')

        print(f'Output log saved to: {output_log_path}')

    # Show and Save Loss Plot
    loss_path = f'{log_folder}run#{run_number}_loss.png'

    plt.plot(train_losses, label='Training Loss')
    plt.plot(val_losses, label='Validation Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.title(f'{model_name} Training and Validation Loss')
    plt.savefig(loss_path)
    print(f'Loss Diagram Saved To: {loss_path}')
    plt.close()

    # Show and Save Accuracy Plot
    acc_path = f'{log_folder}run#{run_number}_accuracy.png'

    plt.plot(train_accuracies, label='Training Accuracy')
    plt.plot(val_accuracies, label='Validation Accuracy')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()
    plt.title(f'{model_name} Training and Validation Accuracy')
    plt.savefig(acc_path)
    print(f'Accuracy Diagram Saved To: {acc_path}')
    plt.close()

    # Save the results to Excel with run number and date
    if save_excel:
        write_results_to_excel(excel_filename, run_number, current_datetime, user_input, num_epochs, train_accuracy, train_precision, train_recall, train_f1_score, val_accuracy, val_precision, val_recall, val_f1_score, train_losses, val_losses)

    # Display and save confusion matrices as images
    plot_confusion_matrix(train_confusion_matrix, classes=['0', '1'], title=f'Training Matrix', path=f'{log_folder}train_confusion_matrix_epoch_{epoch+1}.png')
    plot_confusion_matrix(val_confusion_matrix, classes=['0', '1'], title=f'Test Matrix', path=f'{log_folder}val_confusion_matrix_epoch_{epoch+1}.png')

    return run_number, combined_model, train_losses, val_losses

# Function to write the results to Excel
def write_results_to_excel(filename, run_number, current_datetime, user_input, num_epochs, train_accuracy, train_precision, train_recall, train_f1, val_accuracy, val_precision, val_recall, val_f1, train_losses, val_losses):
    if not os.path.exists(filename):
        df = pd.DataFrame(columns=["Run #", "Date", "Model", "Epochs", "Train Accuracy", "Train Loss", "Train Precision", "Train Recall", "Train F1", "Val Accuracy", "Val Loss", "Val Precision", "Val Recall", "Val F1"])
    else:
        df = pd.read_excel(filename)
    model = ''
    if user_input == '1':
        model = 'GPM'
    elif user_input == '2':
        model = 'GP'
    elif user_input == '3':
        model = 'GPM2'
    elif user_input == '4':
        model = 'GPM2-opt'
    elif user_input == '5':
        model = 'GP-opt'
    elif user_input == '6':
        model = 'GPM-opt'

    # Format the accuracy with 2 decimal points and others with at most 4 decimal points
    train_accuracy_str = "{:.2f}%".format(train_accuracy)
    train_precision_str = "{:.4f}".format(train_precision)
    train_recall_str = "{:.4f}".format(train_recall)
    train_f1_str = "{:.4f}".format(train_f1)
    val_accuracy_str = "{:.2f}%".format(val_accuracy)
    val_precision_str = "{:.4f}".format(val_precision)
    val_recall_str = "{:.4f}".format(val_recall)
    val_f1_str = "{:.4f}".format(val_f1)
    train_loss_str = "{:.4f}".format(train_losses[-1]) 
    val_loss_str = "{:.4f}".format(val_losses[-1])

    new_row = pd.Series({"Run #": run_number,
                         "Date": current_datetime,
                         "Model": model,
                         "Epochs": num_epochs,
                         "Train Accuracy": train_accuracy_str,
                         "Train Loss": train_loss_str,
                         "Train Precision": train_precision_str,
                         "Train Recall": train_recall_str,
                         "Train F1": train_f1_str,
                         "Val Accuracy": val_accuracy_str,
                         "Val Loss": val_loss_str,
                         "Val Precision": val_precision_str,
                         "Val Recall": val_recall_str,
                         "Val F1": val_f1_str})

    df = df.append(new_row, ignore_index=True)
    
    # Create logs folder if missing
    if not os.path.exists('logs/'):
        os.makedirs("logs/")

    df.to_excel(filename, index=False)

    print ("Results saved to: ", filename)

