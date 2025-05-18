import requests
import json

api_url = "http://localhost:5000/predict"
# Ensure you have these test images
image_paths = [
    r"Path to Image\shoe.jpg",
    r"Path to Image\hat.jpg"
]

files_to_send = []
for img_path in image_paths:
    files_to_send.append(('image_files', (open(img_path, 'rb')))) # Tuple: (fieldname, file_object)

try:
    response = requests.post(api_url, files=files_to_send)
    response.raise_for_status()
    print("Status Code:", response.status_code)
    print("Response JSON:", json.dumps(response.json(), indent=2))
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response content: {e.response.text}")
finally:
    for _, file in files_to_send:
        file.close()
