web: gunicorn qubitgyan.wsgi:application
worker: celery -A qubitgyan worker -l info
beat: celery -A qubitgyan beat -l info
