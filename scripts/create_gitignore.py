# File: create_gitignore.py
ignore_content = """
# Django
*.log
*.pot
*.pyc
__pycache__/
db.sqlite3
media/
staticfiles/

# Environment
.env
venv/
.venv/

# IDE/Android
.idea/
.vscode/
"""

with open(".gitignore", "w") as f:
    f.write(ignore_content)

print("✅ Created .gitignore file. You are safe to deploy.")
