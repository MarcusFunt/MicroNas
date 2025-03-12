#!/usr/bin/env python3
import os
import sys
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

def main():
    try:
        # Load environment variables from .env file (if present)
        load_dotenv()
        secret_key = os.environ.get('SECRET_KEY')
        if secret_key:
            print("Successfully loaded SECRET_KEY from .env")
        else:
            print("SECRET_KEY not found in .env; using a fallback for testing purposes.")

        # Create a simple Flask app
        app = Flask(__name__)
        app.config['SECRET_KEY'] = secret_key or 'fallback-secret-key'
        print("Flask imported and app instance created successfully.")

        # Initialize CSRF protection to test Flask-WTF
        csrf = CSRFProtect(app)
        print("CSRFProtect imported and initialized successfully.")

        print("All dependencies imported and basic functionality is working.")
    except Exception as e:
        print("An error occurred during testing:")
        print(e)
        sys.exit(1)

if __name__ == '__main__':
    main()
