"""
WSGI entry point for AWS Elastic Beanstalk deployment
This file allows AWS Elastic Beanstalk to find the Flask application
"""
import sys
import os

# Get the absolute path to the project root (where wsgi.py is located)
project_root = os.path.dirname(os.path.abspath(__file__))

# Add project root to Python path (so we can import wsgi module itself)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add backend directory to Python path (so we can import app from backend)
backend_dir = os.path.join(project_root, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# DO NOT change working directory - this breaks Gunicorn's module resolution
# Instead, ensure all imports use absolute paths from sys.path

# Import the Flask app from backend
# This import will work because backend_dir is in sys.path
from app import app

# WSGI application object (required by Gunicorn/WSGI servers)
# Gunicorn looks for this 'application' variable
application = app

if __name__ == "__main__":
    # For local testing only
    app.run(host='0.0.0.0', port=8000)


