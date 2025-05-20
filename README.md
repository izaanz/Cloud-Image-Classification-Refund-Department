# Refund Item Classifier 🛍️➡️🤖

This project is part of the course: DLBDSMTP01 – Project: From Model to Production

This project automatically classifies pictures of returned clothing items using a smart image recognition model (CNN Transfer Learning on top of Xception). It's designed to help an online store sort refunds faster!

Think of it like this:
1. New refund pictures arrive.
2. Our system "looks" at them.
3. It predicts their categories (like "T-shirt", "Dress", "Shoes").

This README helps you run it on your own computer (locally) or on the internet (AWS cloud).

## What's Inside? 📁

- `app.py`: The "brain" - a Flask web service that does the image classification.
- `test_api.py`: To test the local server by sending image.
- `test_docker.py`: To test locally deployed docker server.
- `batch_processor.py`: A script to process many images at once (for local use).
- `lambda_function.py`: The script for AWS Lambda to process images in the cloud.
- `Dockerfile`: Instructions to package `app.py` into a portable "Docker container".
- `.dockerignore`: Contains instructions to ignore following files from docker: `batch_procesor.py`, `test_api.py`, `test_docker.py`, `lambda_function.py`
- `requirements.txt`: List of Python tools needed.
- `cnn_14_0.889.h5`: The trained CNN model.
- `cnn-model.ipynb` - Jupyter notebook containing the process of training the model.
- `README.md`: This guide!

## Getting Started (On Your Computer - Locally) 💻

This is great for testing and understanding how it works locally.

### 1. Setup Your Project:

- **Get the code:**  
  ```bash
  git clone https://github.com/izaanz/Cloud-Image-Classification-Refund-Department.git
  cd Cloud-Image-Classification-Refund-Department
  ```

- **Python Power-Up (Virtual Environment):**
  ```bash
  python -m venv .venv
  # Windows:
  .venv\Scripts\activate
  # macOS/Linux:
  # source .venv/bin/activate
  ```

- **Install Tools:**  
  `requirements.txt` has: `Flask`, `tensorflow-cpu`, `Pillow`, `numpy`, `requests`.
  Use `tensorflow` instead of `tensorflow-cpu` if you have a GPU capable of compute, or deploying in a server that has GPU. Else, use CPU for AWS.
  Then run:  
  ```bash
  pip install -r requirements.txt
  ```

- **Model:** Trained Model available `cnn_14_0.889.h5` file in the main project folder.

- **Edit Settings:**
  - In `app.py`: Check `MODEL_PATH`.
  - In `batch_processor.py`: Change folder paths like `NEW_IMAGES_DIR` to where you'll keep your test images (e.g., `C:\MyRefundProject\NewImages`).

- **Make Folders:** Create the image folders you set in `batch_processor.py`, if they don't exist already.

### 2. Run the "Brain" (Flask API):

Open a terminal and run:
```bash
python app.py
```
This starts a mini web server, usually at `http://localhost:5000`.

- You can also check if its loaded properly by visiting `http://localhost:5000/health` - This will return status OK if the model is loaded properly

### 3. Testing Locally:

- Use the `test_api.py` to test the locally ran server - make sure to specify test image in `test_api.py`.
- If using Docker to run locally - use `test_docker.py` to test Docker locally.

### 4. Process Images in Batches:

- Make sure `app.py` is still running in its terminal.
- Put some test `.jpg` or `.png` images in your `NEW_IMAGES_DIR`.
- Open a *new* terminal and run:
  ```bash
  python batch_processor.py
  ```

- **Check Results:** Look at the terminal output, the CSV log file it creates, and see if images moved from `New` to `Processed` or `Failed` folders.
- The model and the script is capable of detecting the following 10 classes:
  ```python
  'dress',
  'hat',
  'longsleeve',
  'outwear',
  'pants',
  'shirt',
  'shoes',
  'shorts',
  'skirt',
  't-shirt'
  ```

### 5. (Optional) Schedule it for Nightly Runs (Windows):

- Search "Task Scheduler" in Windows.
- "Create Basic Task..."
- Follow prompts: Set it to run daily (e.g., 2 AM).
- Action: "Start a program".
  - Program: Full path to `python.exe` (inside your `.venv\Scripts\` folder).
  - Arguments: Full path to your `batch_processor.py` script.
  - Start in: Full path to your project folder.
- **Remember:** Your `app.py` (the "brain") needs to be running when the task starts!

## Going to the Cloud (AWS) ☁️🚀

This lets your project run online, accessible from anywhere.

### Cloud Tools You'll Need:

- An AWS Account.
- AWS CLI (like a remote control for AWS from your terminal).
- Docker Desktop (to build your app "container").

### Steps:

#### 1. "Dockerize" Your App (Package it up):

- Your `app.py` should be the version that takes image *files*, not just paths.
- Your `Dockerfile` tells Docker how to build an image of your app.
- Your `requirements.txt` should include `gunicorn` for this.
- **Build the Docker image:**
  ```bash
  docker build -t refund-classifier-api .
  ```

- **Test it locally first:**  
  ```bash
  docker run -p 5001:80 refund-classifier-api
  ```  
  Test `http://localhost:5001/predict` by sending image files.

#### 2. Set Up AWS Resources:

- **S3 (Storage):**
  - Create an S3 bucket (e.g., `my-refund-app-images`).
  - Make "folders" inside: `new-images/`, `processed-images/`, `failed-images/`, `reports/`.

- **ECR (Docker Image Storage):**
  - Create an ECR repository (e.g., `refund-classifier-api`).
  - "Push" your Docker image to ECR (AWS console gives you commands for this).

- **IAM Roles (Permissions):**
  - `EC2-Role`: Lets your EC2 server pull images from ECR.
  - `Lambda-Role`: Lets your Lambda function talk to S3.

- **EC2 (Virtual Server to Run API):**
  - Launch a `t2.micro` (free tier!) Amazon Linux 2 instance.
  - Assign the `EC2-Role`.
  - Security Group: Allow HTTP (port 80) from `Anywhere` (so Lambda can reach it).
  - **User Data (script to run on startup):** Tell EC2 to install Docker, log into ECR, pull your image, and run it.
  - Get the EC2's Public IP address.

- **Lambda (Code to Run the Batch Job):**
  - Create a Lambda function using Python.
  - Use `lambda_function.py` as the code.
  - Assign the `Lambda-Role`.
  - **Environment Variables:**
    - `S3_BUCKET_NAME`: Your S3 bucket name.
    - `API_ENDPOINT`: `http://<YOUR_EC2_PUBLIC_IP>/predict`
  - Set memory (e.g., 512MB) and timeout (e.g., 3-5 minutes).
  - **If `lambda_function.py` needs extra libraries (like `requests`):** Create a "deployment package" (a zip file with your code and libraries) and upload it.

- **EventBridge (Scheduler):**
  - Create a schedule to run your Lambda function nightly (e.g., using a cron expression like `cron(0 2 * * ? *)` for 2 AM UTC).

### 3. Test Your Cloud Setup:

- **Test API on EC2:** Go to `http://<EC2_PUBLIC_IP>/health` in your browser. Send test images to `http://<EC2_PUBLIC_IP>/predict`.

- **Test Full Flow:**
  - Upload test images to `s3://your-bucket/new-images/`.
  - Run your Lambda function manually from the AWS console (or wait for the schedule).
  - Check CloudWatch Logs (for Lambda).
  - Check S3: Images should move, and a report CSV should appear in `reports/`.

## Key Settings ⚙️

- **`app.py`:**
  - `MODEL_PATH`: Location of your `.h5` model file.
  - `CLASS_NAMES`: Your list of 10 clothing categories.

- **`batch_processor.py` (Local):**
  - Folder paths for images and reports.

- **`lambda_function.py` (AWS Lambda - Environment Variables):**
  - `S3_BUCKET_NAME`: Your S3 bucket.
  - `API_ENDPOINT`: URL of your API running on EC2.

## Tips ✨

- **Start Simple:** Get the local version working perfectly before moving to AWS.
- **Test Each Part:** When on AWS, test your EC2 API first, then Lambda, then the scheduler.
- **Check Logs:** CloudWatch Logs (for Lambda) and `docker logs` (on EC2) are your best friends for debugging.
- **Free Tier:** Be mindful of AWS Free Tier limits to avoid unexpected bills.
