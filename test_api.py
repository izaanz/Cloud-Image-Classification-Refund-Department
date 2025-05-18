import requests
import json

# Ensure you have some images at these paths for testing
test_image_paths = [
    r"Path to Image\hat.jpg",
    r"Path to Image\tshirt2.jpg"
]

api_url = "http://localhost:5000/predict" # Or http://127.0.0.1:5000/predict

payload = {"image_paths": test_image_paths}

try:
    response = requests.post(api_url, json=payload)
    response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
    
    print("Status Code:", response.status_code)
    print("Response JSON:", json.dumps(response.json(), indent=2))

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
except json.JSONDecodeError:
    print(f"Failed to decode JSON. Response content: {response.text}")
