import os
import random
import string
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file):
    if file and allowed_file(file.filename):
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Generate a unique filename
        unique_filename = f"{random_string(10)}_{filename}"

        # Set the path to save the file (adjust `UPLOAD_FOLDER` path as needed)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        filepath = os.path.join(upload_folder, unique_filename)

        # Save the file
        file.save(filepath)

        # Return the file URL or path
        return f'uploads/{unique_filename}'

    return None

def random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
