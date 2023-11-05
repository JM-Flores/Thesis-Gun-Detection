import torch
import torch.optim as optim
from torch.utils.data import DataLoader
import time

def train_model(train_loader, val_loader, combined_model, criterion, optimizer, device, num_epochs):
    train_losses = []  # To store training losses for each epoch
    val_losses = []    # To store validation losses for each epoch

    for epoch in range(num_epochs):
        start_time = time.time()
        combined_model.train()
        total_train_loss = 0
        correct = 0
        total = 0

        for batch in train_loader:
            data_name, gun_data, pose_data, motion_data, target_labels = batch

            gun_data = gun_data.to(device)
            pose_data = pose_data.to(device)
            motion_data = motion_data.to(device)
            target_labels = target_labels.to(device)

            optimizer.zero_grad()

            combined_output = combined_model(gun_data, pose_data, motion_data)

            _, predicted = torch.max(combined_output, 1)  # Get the class with the highest probability
            total += target_labels.size(0)  # Accumulate the total number of examples
            correct += (predicted == target_labels).sum().item()  # Count correct predictions

            loss = criterion(combined_output, target_labels)
            loss.backward()
            optimizer.step()

            total_train_loss += loss.item()

        train_accuracy = 100 * correct / total

        average_train_loss = total_train_loss / len(train_loader)
        train_losses.append(average_train_loss)

        # Validation loop
        combined_model.eval()  # Set the model to evaluation mode
        total_val_loss = 0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in val_loader:
                data_name, gun_data, pose_data, motion_data, target_labels = batch

                gun_data = gun_data.to(device)
                pose_data = pose_data.to(device)
                motion_data = motion_data.to(device)
                target_labels = target_labels.to(device)

                combined_output = combined_model(gun_data, pose_data, motion_data)

                _, predicted = torch.max(combined_output, 1)  # Get the class with the highest probability
                total += target_labels.size(0)  # Accumulate the total number of examples
                correct += (predicted == target_labels).sum().item()  # Count correct predictions

                val_loss = criterion(combined_output, target_labels)
                total_val_loss += val_loss.item()

        val_accuracy = 100 * correct / total

        end_time = time.time()  # Record the end time for the epoch
        epoch_time = end_time - start_time  # Calculate the time taken for the epoch
        
        average_val_loss = total_val_loss / len(val_loader)
        val_losses.append(average_val_loss)

        combined_model.train()  # Set the model back to training mode

        print(f'Epoch [{epoch+1}/{num_epochs}], Training Accuracy: {train_accuracy:.2f}%, Training Loss: {average_train_loss:.4f}, Validation Accuracy: {val_accuracy:.2f}%, Validation Loss: {average_val_loss:.4f}, Time: {epoch_time:.2f} seconds')

    return train_losses, val_losses