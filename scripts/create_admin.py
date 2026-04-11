import os
import sys
import django

# 1. Setup Django Environment
# We need to add the project root to Python path to find 'qubitgyan'
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qubitgyan.settings")
django.setup()

from django.contrib.auth import get_user_model
from library.models import UserProfile # Import your profile model

User = get_user_model()

def create_super_admin():
    # 2. Get credentials from Render Environment Variables
    username = os.environ.get('ADMIN_USERNAME')
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')

    if not username or not password:
        print("⚠️ ADMIN_USERNAME or ADMIN_PASSWORD missing in env vars. Skipping admin creation.")
        return

    # 3. Check if user exists
    if not User.objects.filter(username=username).exists():
        print(f"Creating Superuser: {username}...")
        
        # Create the user
        admin_user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        # 4. CRITICAL FIX: Create the Profile explicitly
        # This prevents the 500 Error by ensuring the row exists immediately
        UserProfile.objects.create(
            user=admin_user, 
            created_by=admin_user, # They created themselves
            is_suspended=False
        )
        
        print(f"✅ Superuser '{username}' and UserProfile created successfully!")
    
    else:
        print(f"User '{username}' already exists. Checking profile integrity...")
        
        # Self-Healing for existing user (if you didn't wipe DB)
        user = User.objects.get(username=username)
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user, created_by=user)
            print("✅ Fixed missing profile for existing admin.")
        else:
            print("✅ Profile already exists.")

if __name__ == "__main__":
    create_super_admin()
