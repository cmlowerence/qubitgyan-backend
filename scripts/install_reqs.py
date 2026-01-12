# File: install_reqs.py
import sys
import subprocess

packages = [
    "Django==5.0.1",
    "djangorestframework==3.14.0",
    "gunicorn==21.2.0",          # Required for Render
    "psycopg2-binary==2.9.9",    # Required for Postgres (Render DB)
    "dj-database-url==2.1.0",    # To parse database URLs
    "whitenoise==6.6.0",         # To serve static files on Render
    "django-cors-headers==4.3.1" # To allow Next.js to talk to Django
]

print("🚀 Installing QubitGyan dependencies...")
for package in packages:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Installed {package}")
    except Exception as e:
        print(f"❌ Failed to install {package}: {e}")

print("\n🎉 All dependencies installed!")
