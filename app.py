from flask import Flask, request, jsonify
import tensorflow as tf
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.xception import preprocess_input
import numpy as np
import os
import io 

app = Flask(__name__)

# --- Configuration ---
MODEL_PATH = 'model/cnn_14_0.889.h5' # Model will be in the Docker image
IMAGE_SIZE = (299, 299)
CLASS_NAMES = [
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
    ] # 10 classes


# --- Load Model ---
# Ensure model is loaded once when the app starts
try:
    model = tf.keras.models.load_model(MODEL_PATH)
    print(f"Model loaded from {MODEL_PATH}")
except Exception as e:
    model = None
    print(f"Error loading model: {e}. Predictions will fail.")


def preprocess_image_data(img_bytes):
    img = image.load_img(io.BytesIO(img_bytes), target_size=IMAGE_SIZE)
    img_array = image.img_to_array(img)
    img_array_expanded = np.expand_dims(img_array, axis=0)
    return preprocess_input(img_array_expanded)

@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500

    if 'image_files' not in request.files: # Expecting multiple files
        return jsonify({'error': 'Missing "image_files" in form-data'}), 400

    image_files = request.files.getlist('image_files') # Get list of files
    
    results = []
    try:
        for file_storage_object in image_files:
            filename = file_storage_object.filename
            try:
                img_bytes = file_storage_object.read()
                processed_image = preprocess_image_data(img_bytes)
                predictions = model.predict(processed_image)
                probabilities = predictions[0].tolist()
                predicted_class_index = np.argmax(probabilities)
                predicted_class_name = CLASS_NAMES[predicted_class_index]
                
                results.append({
                    'filename': filename,
                    'predicted_class': predicted_class_name,
                    'predicted_class_index': int(predicted_class_index),
                    'probabilities': {CLASS_NAMES[i]: float(prob) for i, prob in enumerate(probabilities)}
                })
            except Exception as e_file:
                app.logger.error(f"Error processing file {filename}: {e_file}")
                results.append({
                    'filename': filename,
                    'error': f'Error processing file: {str(e_file)}'
                })
        return jsonify(results), 200

    except Exception as e_batch:
        app.logger.error(f"Error during batch prediction: {e_batch}")
        return jsonify({'error': str(e_batch)}), 500
    
@app.route('/health', methods=['GET'])
def health_check():
    # Basic health check
    return jsonify({"status": "ok", "model_loaded": model is not None}), 200

if __name__ == '__main__':
    # For Docker, Gunicorn will typically be used instead of app.run()
    # This is fine for local testing: python app.py
    app.run(host='0.0.0.0', port=5000, debug=True)
