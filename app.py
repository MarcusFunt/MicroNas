import os
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, send_file, abort, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
from flask_wtf.csrf import CSRFProtect
from config import Config
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Set up CSRF protection for all forms
csrf = CSRFProtect(app)

# New route to serve the favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# New route to serve the homemade logo (logo.svg)
@app.route('/logo.svg')
def logo():
    return send_from_directory(app.root_path, 'logo.svg', mimetype='image/svg+xml')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------
# Setup file logging for events:
# Only log UPLOAD, DELETE and errors.
# Logs are rotated every 48 hours (keeping only current 48 hours of logs).
# -------------------------------
log_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

file_handler = TimedRotatingFileHandler(log_file, when='h', interval=48, backupCount=0)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

class EventFilter(logging.Filter):
    def filter(self, record):
        # Always allow error-level logs.
        if record.levelno >= logging.ERROR:
            return True
        # Allow only messages that contain "UPLOAD:" or "DELETE:".
        message = record.getMessage()
        if "UPLOAD:" in message or "DELETE:" in message:
            return True
        return False

file_handler.addFilter(EventFilter())
logger.addHandler(file_handler)

# -------------------------------
# Parse admin credentials from the config.
# Expecting entries like "admin1:pass1,admin2:pass2" in ADMIN_USERS environment variable.
ADMIN_CREDENTIALS = {}
for cred in app.config['ADMIN_USERS']:
    try:
        username, password = cred.split(':')
        ADMIN_CREDENTIALS[username.strip()] = password.strip()
    except ValueError:
        continue

# Helper: Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Decorator to require login for protected routes
def requires_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Define pagination settings
ITEMS_PER_PAGE = 20

# Route: Browse directories and files with pagination
@app.route('/')
def index():
    rel_path = request.args.get('path', '')
    page = int(request.args.get('page', 1))
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], rel_path))

    if not abs_path.startswith(app.config['UPLOAD_FOLDER']):
        abort(403)

    if os.path.isfile(abs_path):
        return send_file(abs_path)

    try:
        entries = os.listdir(abs_path)
    except Exception as e:
        logger.error("ERROR: %s", str(e))
        flash('Error accessing directory.')
        entries = []

    items = []
    for entry in entries:
        full_path = os.path.join(abs_path, entry)
        rel_entry = os.path.join(rel_path, entry)
        items.append({
            'name': entry,
            'path': rel_entry,
            'is_dir': os.path.isdir(full_path)
        })

    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    # Simple pagination logic
    total_items = len(items)
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_items = items[start:end]

    return render_template('index.html',
                           items=paginated_items,
                           current_path=rel_path,
                           page=page,
                           total_items=total_items,
                           items_per_page=ITEMS_PER_PAGE,
                           logged_in=session.get('logged_in', False))

# Route: Search PDFs by filename (PDF content search removed)
@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    results = []
    if query:
        for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
            for file in files:
                if file.lower().endswith('.pdf'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, app.config['UPLOAD_FOLDER'])
                    if query in file.lower():
                        results.append({'name': file, 'path': rel_path})
    return render_template('search.html', query=query, results=results, logged_in=session.get('logged_in', False))

# Route: Serve a PDF file
@app.route('/view/<path:filename>')
def view_file(filename):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    if not abs_path.startswith(app.config['UPLOAD_FOLDER']) or not os.path.isfile(abs_path):
        abort(403)
    return send_file(abs_path)

# Route: Upload PDFs (Protected) with graphical subdirectory selector and create new folder option
@app.route('/upload', methods=['GET', 'POST'])
@requires_login
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file chosen')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # Validate file header to ensure it's a PDF by checking for the %PDF marker
            file.stream.seek(0)
            header = file.stream.read(4)
            file.stream.seek(0)
            if header != b'%PDF':
                flash('Uploaded file is not a valid PDF.')
                return redirect(request.url)
            filename = secure_filename(file.filename)
            # Get the selected existing subdirectory
            target_path = request.form.get('path', '')
            # Check if a new subdirectory name is provided, override if so
            new_path = request.form.get('new_path', '').strip()
            if new_path:
                target_path = new_path
            dest_dir = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], target_path))
            if not dest_dir.startswith(app.config['UPLOAD_FOLDER']):
                abort(403)
            os.makedirs(dest_dir, exist_ok=True)
            file.save(os.path.join(dest_dir, filename))
            flash('File uploaded successfully')
            # Log the upload event with the admin username from session.
            logger.info("UPLOAD: User '%s' uploaded file '%s' to '%s'",
                        session.get('username', 'unknown'), filename, target_path)
            return redirect(url_for('index', path=target_path))
    # For GET requests, list available subdirectories graphically
    upload_folder = app.config['UPLOAD_FOLDER']
    subdirs = []
    try:
        for d in os.listdir(upload_folder):
            full_path = os.path.join(upload_folder, d)
            if os.path.isdir(full_path):
                subdirs.append(d)
    except Exception as e:
        subdirs = []
    return render_template('upload.html', logged_in=session.get('logged_in', False), subdirs=subdirs)

# Route: Delete a File or Folder (Protected)
@app.route('/delete/<path:filename>', methods=['POST'])
@requires_login
def delete_file(filename):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    if not abs_path.startswith(app.config['UPLOAD_FOLDER']):
        abort(403)
    if os.path.isfile(abs_path):
        os.remove(abs_path)
        flash(f'File "{filename}" deleted successfully')
    elif os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
        flash(f'Folder "{filename}" deleted successfully')
    else:
        flash("The item does not exist")
    # Log the deletion event with the admin username.
    logger.info("DELETE: User '%s' deleted '%s'", session.get('username', 'unknown'), filename)
    return redirect(url_for('index'))

# Route: Admin-only view of system logs (uploads, deletions, errors)
@app.route('/logs')
@requires_login
def view_logs():
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        lines = [f"Unable to read log file: {e}"]
    return render_template('logs.html', logs=lines, logged_in=session.get('logged_in', False))

# Route: Login (with support for multiple admin users)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == password:
            session['logged_in'] = True
            session['username'] = username  # Save the username for logging purposes.
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
            return redirect(url_for('login'))
    return render_template('login.html', logged_in=session.get('logged_in', False))

# Route: Logout
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash("You have been logged out.")
    return redirect(url_for('index'))

# Optional: Global error handler to log unhandled exceptions.
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error("ERROR: %s", str(e))
    return render_template("error.html", error=str(e)), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
