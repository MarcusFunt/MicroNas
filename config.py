import os

class Config:
    # Load sensitive values from environment variables or use a default (change in production!)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-secret-key')
    # Expecting ADMIN_USERS as a comma-separated list like "admin1:pass1,admin2:pass2"
    ADMIN_USERS = os.environ.get('ADMIN_USERS', 'admin:password').split(',')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    UPLOAD_FOLDER = os.path.abspath('pdf_notes')
    ALLOWED_EXTENSIONS = {'pdf'}
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300  # seconds
