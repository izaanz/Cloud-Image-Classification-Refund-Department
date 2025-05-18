import os
import glob
import requests
import datetime
import shutil
import json
import csv
import time # For potential retries or delays

# --- Configuration ---
# Make sure the RefundImages Folder exists with the following sub-folders
# New, Processed, Failed, RefundReports
NEW_IMAGES_DIR = r"Path to folder\RefundImages\New"
PROCESSED_IMAGES_DIR_BASE = r"Path to folder\RefundImages\Processed"
FAILED_IMAGES_DIR_BASE = r"Path to folder\RefundImages\Failed"
REPORTS_DIR = r"Path to folder\RefundReports" 
CLASSIFICATION_LOG_FILE = os.path.join(REPORTS_DIR, "classification_log.csv")
API_URL = "http://localhost:5000/predict" # Flask API URL

# Ensure directories exist
os.makedirs(NEW_IMAGES_DIR, exist_ok=True)
os.makedirs(PROCESSED_IMAGES_DIR_BASE, exist_ok=True)
os.makedirs(FAILED_IMAGES_DIR_BASE, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# --- CSV Log Setup ---
CSV_HEADER = ['timestamp', 'original_image_path', 'processed_image_path', 'status',
              'predicted_class', 'predicted_class_index', 'probabilities_json']

if not os.path.exists(CLASSIFICATION_LOG_FILE):
    with open(CLASSIFICATION_LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

def log_to_csv(data_row):
    with open(CLASSIFICATION_LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            data_row.get('timestamp'),
            data_row.get('original_image_path'),
            data_row.get('processed_image_path'),
            data_row.get('status'),
            data_row.get('predicted_class'),
            data_row.get('predicted_class_index'),
            data_row.get('probabilities_json')
        ])

def process_images_in_batches(image_paths, batch_size=10):
    all_api_results = []
    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i:i + batch_size]
        print(f"Processing batch of {len(batch_paths)} images...")
        payload = {"image_paths": batch_paths}
        try:
            response = requests.post(API_URL, json=payload, timeout=120) # Timeout of 2 mins
            response.raise_for_status()
            results = response.json()
            all_api_results.extend(results)
        except requests.exceptions.RequestException as e:
            print(f"API call failed for batch starting with {batch_paths[0] if batch_paths else 'N/A'}: {e}")
            # Mark these images as failed for API call
            for path in batch_paths:
                all_api_results.append({'image_path': path, 'error': f'API request failed: {e}'})
        except Exception as e: # Catch any other unexpected errors from the API or JSON parsing
            print(f"An unexpected error occurred for batch: {e}")
            for path in batch_paths:
                 all_api_results.append({'image_path': path, 'error': f'Unexpected error: {e}'})
        time.sleep(1) # Small delay between batches if needed
    return all_api_results

def main():
    print(f"Starting batch processing at {datetime.datetime.now()}")

    # Find new images (jpg, png, jpeg)
    image_extensions = ("*.jpg", "*.jpeg", "*.png")
    new_image_files = []
    for ext in image_extensions:
        new_image_files.extend(glob.glob(os.path.join(NEW_IMAGES_DIR, ext)))

    if not new_image_files:
        print("No new images found to process.")
        return

    print(f"Found {len(new_image_files)} new images.")

    # Send image paths to API in batches
    api_results = process_images_in_batches(new_image_files, batch_size=10) # Adjust batch_size as needed

    # Create dated subdirectories for processed/failed images
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    current_processed_dir = os.path.join(PROCESSED_IMAGES_DIR_BASE, today_str)
    current_failed_dir = os.path.join(FAILED_IMAGES_DIR_BASE, today_str)
    os.makedirs(current_processed_dir, exist_ok=True)
    os.makedirs(current_failed_dir, exist_ok=True)

    # Process results and move files
    for result in api_results:
        original_path = result['image_path']
        filename = os.path.basename(original_path)
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'original_image_path': original_path,
            'processed_image_path': '',
            'status': '',
            'predicted_class': '',
            'predicted_class_index': '',
            'probabilities_json': ''
        }

        if 'error' in result:
            print(f"Error processing {original_path}: {result['error']}")
            destination_path = os.path.join(current_failed_dir, filename)
            log_entry['status'] = 'failed'
            log_entry['processed_image_path'] = destination_path
            # Add more error details if available from result['error']
        else:
            destination_path = os.path.join(current_processed_dir, filename)
            log_entry['status'] = 'processed'
            log_entry['processed_image_path'] = destination_path
            log_entry['predicted_class'] = result.get('predicted_class')
            log_entry['predicted_class_index'] = result.get('predicted_class_index')
            log_entry['probabilities_json'] = json.dumps(result.get('probabilities'))
            print(f"Processed {original_path}: Class={result.get('predicted_class')}")
        
        try:
            shutil.move(original_path, destination_path)
            print(f"Moved {original_path} to {destination_path}")
        except Exception as e:
            print(f"Error moving {original_path} to {destination_path}: {e}")
            # If move fails, update status or log separately
            log_entry['status'] = 'move_failed'
            # Potentially try to copy and then delete if move is problematic across drives/permissions

        log_to_csv(log_entry)

    print(f"Batch processing finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    main()
