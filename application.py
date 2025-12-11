"""
Alternative WSGI entry point for Elastic Beanstalk
Some EB configurations look for application.py instead of wsgi.py
This file imports from wsgi.py to ensure compatibility
"""
import sys
import os

# Elastic Beanstalk deployment directory
EB_DEPLOY_DIR = '/var/app/current'

# Get the directory where this file is located
current_file_dir = os.path.dirname(os.path.abspath(__file__))

# Determine project root
if os.path.exists(EB_DEPLOY_DIR) and os.path.exists(os.path.join(EB_DEPLOY_DIR, 'wsgi.py')):
    project_root = EB_DEPLOY_DIR
else:
    project_root = current_file_dir

# Add project root to Python path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add backend directory to Python path
backend_dir = os.path.join(project_root, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import from wsgi.py (which handles the Flask app import)
try:
    from wsgi import application
except ImportError:
    # Fallback: import directly from backend
    from app import app
    application = app

if __name__ == "__main__":
    # For local testing only
    if hasattr(application, 'run'):
        application.run(host='0.0.0.0', port=8000)

