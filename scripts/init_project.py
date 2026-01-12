# File: init_project.py
import os
import subprocess
import sys

def run_command(command):
    subprocess.check_call(command, shell=True)

project_name = "qubitgyan"
app_name = "library"

print("🔨 Initializing QubitGyan Backend...")

# 1. Create Django Project
if not os.path.exists(project_name):
    run_command(f"django-admin startproject {project_name} .")
    print(f"✅ Created project '{project_name}'")
else:
    print(f"⚠️ Project folder already exists.")

# 2. Create the 'library' app
if not os.path.exists(app_name):
    run_command(f"python manage.py startapp {app_name}")
    print(f"✅ Created app '{app_name}'")

# 3. Create API folder structure (For our versioning)
api_path = os.path.join(app_name, "api", "v1")
os.makedirs(os.path.join(api_path, "public"), exist_ok=True)
os.makedirs(os.path.join(api_path, "manager"), exist_ok=True)

# Create __init__.py files so Python recognizes them
open(os.path.join(app_name, "api", "__init__.py"), 'a').close()
open(os.path.join(app_name, "api", "v1", "__init__.py"), 'a').close()
open(os.path.join(api_path, "public", "__init__.py"), 'a').close()
open(os.path.join(api_path, "manager", "__init__.py"), 'a').close()

print(f"✅ Created API folder structure in '{app_name}/api/v1/'")

# 4. Create requirements.txt (Crucial for Render deployment)
req_content = """Django==5.0.1
djangorestframework==3.14.0
gunicorn==21.2.0
psycopg2-binary==2.9.9
dj-database-url==2.1.0
whitenoise==6.6.0
django-cors-headers==4.3.1
"""
with open("requirements.txt", "w") as f:
    f.write(req_content)
print("✅ Created requirements.txt")

# 5. Create build.sh (Crucial for Render deployment)
build_content = """#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
"""
with open("build.sh", "w") as f:
    f.write(build_content)
print("✅ Created build.sh (Deployment Script)")

print("\n🚀 Initialization Complete! Ready for Settings configuration.")
