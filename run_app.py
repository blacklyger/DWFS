"""
WSGI entry point, e.g. for gunicorn:

    gunicorn --bind 127.0.0.1:8000 run_app:application
"""

from dwfs import app as application

if __name__ == "__main__":
    # Development server only (never use debug=True in production).
    application.run(host="127.0.0.1", port=5000, debug=False)
