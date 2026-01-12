# File: scripts/create_admin.py
import os
import sys
import django

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
# ----------------

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qubitgyan.settings")
django.setup()

from django.contrib.auth import get_user_model

def manage_superuser():
    User = get_user_model()
    
    # 1. Get configuration from Render Environment (or defaults)
    username = os.environ.get("ADMIN_USERNAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD")

    # Safety: If no password is in the environment, do nothing.
    if not password:
        print("⚠️  No ADMIN_PASSWORD found. Skipping admin management.")
        return

    # 2. Check if user exists
    try:
        user = User.objects.get(username=username)
        
        # 3. USER EXISTS: Update the password (The "Reset" Feature)
        print(f"🔄 User '{username}' found. Syncing password from Environment...")
        user.set_password(password)
        user.email = email  # Update email too, just in case
        user.is_superuser = True # Ensure they are still admin
        user.is_staff = True
        user.save()
        print(f"✅ Password updated for '{username}' successfully!")

    except User.DoesNotExist:
        # 4. USER DOES NOT EXIST: Create new
        print(f"🆕 Creating new superuser: '{username}'")
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"✅ Superuser '{username}' created successfully!")

if __name__ == "__main__":
    manage_superuser()
