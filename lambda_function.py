import json
import boto3
import os
import datetime
import requests
import csv
import io

S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'YOUR_S3_BUCKET_UNQIUE') # Set in Lambda Env Vars
S3_NEW_PREFIX = 'new-images/'
S3_PROCESSED_PREFIX = 'processed-images/'
S3_FAILED_PREFIX = 'failed-images/'
S3_REPORTS_PREFIX = 'reports/'

# Get EC2 API endpoint from Lambda Environment Variables
API_ENDPOINT = os.environ.get('API_ENDPOINT', 'http://YOUR_EC2_IP/predict') # Set in Lambda Env Vars

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    print(f"Starting batch processing. Bucket: {S3_BUCKET_NAME}, Prefix: {S3_NEW_PREFIX}")
    
    try:
        list_response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=S3_NEW_PREFIX)
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
        return {'statusCode': 500, 'body': json.dumps(f"Error listing S3: {e}")}

    if 'Contents' not in list_response:
        print("No new images found.")
        return {'statusCode': 200, 'body': json.dumps('No new images found.')}

    images_to_process = [item['Key'] for item in list_response['Contents'] if item['Key'] != S3_NEW_PREFIX] # Exclude folder itself
    
    if not images_to_process:
        print("No new image files found in prefix.")
        return {'statusCode': 200, 'body': json.dumps('No new image files found.')}

    print(f"Found {len(images_to_process)} images to process.")
    
    # In a real scenario, you might batch these API calls.
    # For simplicity here, processing one by one.
    # To send multiple files in one request to the Flask API:
    files_for_api = []
    s3_object_keys_in_batch = []

    for s3_key in images_to_process:
        try:
            s3_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            image_data = s3_object['Body'].read()
            filename = os.path.basename(s3_key)
            
            # Add to list for batch API call
            files_for_api.append(('image_files', (filename, image_data, s3_object['ContentType'])))
            s3_object_keys_in_batch.append(s3_key)

        except Exception as e:
            print(f"Error downloading {s3_key} or preparing for API: {e}")
            # Move to failed, log error
            move_s3_object(s3_key, S3_FAILED_PREFIX, f"Download/Prep Error: {e}")
            log_result(s3_key, 'failed', {}, error_message=f"Download/Prep Error: {e}")
            continue # Skip to next image if download fails

    # If we have files, make the API call
    api_call_results = []
    if files_for_api:
        try:
            print(f"Sending {len(files_for_api)} files to API: {API_ENDPOINT}")
            response = requests.post(API_ENDPOINT, files=files_for_api, timeout=120) # 2 min timeout
            response.raise_for_status()
            api_call_results = response.json() # Expects a list of results
            print(f"API Response: {api_call_results}")
        except requests.exceptions.RequestException as e:
            print(f"API call failed: {e}")
            # Mark all images in this batch as failed for API call
            for s3_key in s3_object_keys_in_batch:
                move_s3_object(s3_key, S3_FAILED_PREFIX, f"API Request Error: {e}")
                log_result(s3_key, 'failed', {}, error_message=f"API Request Error: {e}")
            api_call_results = [] # Reset so it doesn't try to process old results

    # Process API results and move files
    # Match results from API (which are per-filename) to s3_keys
    # This assumes the API returns results in the same order or includes filename
    # Our modified Flask app returns 'filename' in each result object
    
    processed_filenames_map = {res['filename']: res for res in api_call_results if 'filename' in res}

    for s3_key in s3_object_keys_in_batch: # Iterate through the keys we attempted to send
        filename = os.path.basename(s3_key)
        api_result = processed_filenames_map.get(filename)

        if api_result and 'error' not in api_result:
            print(f"Successfully processed {s3_key}: Class={api_result.get('predicted_class')}")
            move_s3_object(s3_key, S3_PROCESSED_PREFIX)
            log_result(s3_key, 'processed', api_result)
        else:
            error_msg = "API processing error or file not in response"
            if api_result and 'error' in api_result:
                error_msg = api_result['error']
            elif not api_result and files_for_api: # If files were sent but this one is missing in response
                 error_msg = "File processed by API but no result returned or filename mismatch."

            print(f"Failed to process {s3_key}: {error_msg}")
            move_s3_object(s3_key, S3_FAILED_PREFIX, error_msg)
            log_result(s3_key, 'failed', {}, error_message=error_msg)

    return {'statusCode': 200, 'body': json.dumps(f'Processed {len(images_to_process)} images.')}

def move_s3_object(source_key, dest_prefix, error_message=None):
    filename = os.path.basename(source_key)
    dest_key = os.path.join(dest_prefix, filename)
    
    copy_source = {'Bucket': S3_BUCKET_NAME, 'Key': source_key}
    try:
        print(f"Moving {source_key} to {dest_key}")
        s3_client.copy_object(CopySource=copy_source, Bucket=S3_BUCKET_NAME, Key=dest_key)
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=source_key)
    except Exception as e:
        print(f"Error moving {source_key} to {dest_key}: {e}")
        # If move fails, it remains in new-images for next run or manual check

def log_result(s3_key, status, api_result_data, error_message=None):
    timestamp = datetime.datetime.utcnow().isoformat()
    report_filename = f"classification_log_{datetime.datetime.utcnow().strftime('%Y-%m-%d')}.csv"
    report_key = os.path.join(S3_REPORTS_PREFIX, report_filename)
    
    log_entry = {
        'timestamp': timestamp,
        's3_key': s3_key,
        'status': status,
        'predicted_class': api_result_data.get('predicted_class', ''),
        'probabilities': json.dumps(api_result_data.get('probabilities', {})),
        'error': error_message if error_message else api_result_data.get('error', '')
    }
    
    # Check if report CSV exists, if not, write header
    try:
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=report_key)
        existing_file = True
    except:
        existing_file = False

    output_stream = io.StringIO()
    writer = csv.DictWriter(output_stream, fieldnames=log_entry.keys())
    
    if not existing_file:
        writer.writeheader()
    writer.writerow(log_entry)
    
    csv_content = output_stream.getvalue()
    output_stream.close()

    try:
        if existing_file:
            # Append: Get existing, append, then put. S3 PutObject overwrites.
            existing_object = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=report_key)
            existing_content = existing_object['Body'].read().decode('utf-8')
            if not existing_content.endswith('\n'):  # Ensure newline before appending
                existing_content += '\n'
            
            lines = csv_content.splitlines()
            if len(lines) >= 2:
                csv_content = existing_content + lines[1] + '\n'
            else:
                print(f"Unexpected CSV content when logging {s3_key}: {lines}")
                csv_content = existing_content  # Avoid crash


        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=report_key, Body=csv_content.encode('utf-8'), ContentType='text/csv')
        print(f"Logged result for {s3_key} to {report_key}")
    except Exception as e:
        print(f"Error writing log to S3 for {s3_key}: {e}")

# For testing locally (if you have AWS CLI configured and boto3 installed)
# if __name__ == '__main__':
#    os.environ['S3_BUCKET_NAME'] = 'your-actual-bucket-name-for-testing'
#    os.environ['API_ENDPOINT'] = 'http://your_ec2_public_ip/predict' # Your actual EC2 endpoint
#    # Create a dummy new-images/test.jpg in your S3 bucket
#    lambda_handler({}, None)
