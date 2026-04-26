import cv2
import numpy as np
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
import os
import logging

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
logging.getLogger('tensorflow').setLevel(logging.ERROR)

print("Đang tải mô hình AI MobileNetV2...")
face_model = MobileNetV2(weights='imagenet', include_top=False, pooling='avg', input_shape=(224, 224, 3))
print("Tải AI thành công!")

def get_face_embedding(img_bytes: bytes) -> list:
    try:
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            return None

        img_resized = cv2.resize(img, (224, 224))

        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_array = np.expand_dims(img_rgb, axis=0)
        img_preprocessed = preprocess_input(img_array)

        embedding = face_model.predict(img_preprocessed, verbose=0)[0]

        return embedding.tolist()
        
    except Exception as e:
        print(f"Lỗi AI trích xuất khuôn mặt: {e}")
        return None