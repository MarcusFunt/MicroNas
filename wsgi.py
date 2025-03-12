from app import app

if __name__ == '__main__':
    # This block is useful for debugging via command line,
    # but in production you would run Gunicorn or uWSGI, which import 'app' from this file.
    app.run(host='0.0.0.0', port=5000)
