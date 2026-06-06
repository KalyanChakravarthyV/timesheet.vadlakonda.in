.PHONY: install migrate superuser run celery beat shell test lint

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

run:
	python manage.py runserver 0.0.0.0:8000

celery:
	celery -A config.celery worker --loglevel=info

beat:
	celery -A config.celery beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

shell:
	python manage.py shell

test:
	python manage.py test timesheets --verbosity=2

lint:
	python -m flake8 . --max-line-length=100 --exclude=migrations,venv,.venv

# Alembic helpers
alembic-upgrade:
	alembic upgrade head

alembic-downgrade:
	alembic downgrade -1

alembic-history:
	alembic history

# Weekly email — last completed week
send-weekly:
	python manage.py send_weekly_timesheets

# Weekly email — dry-run
send-weekly-dry:
	python manage.py send_weekly_timesheets --dry-run
