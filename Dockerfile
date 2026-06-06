FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
# Extract and install dependencies from pyproject.toml without building the project wheel
RUN python3 -c "\
import tomllib, subprocess, sys; \
data = tomllib.load(open('pyproject.toml', 'rb')); \
deps = data['project']['dependencies']; \
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir'] + deps)"

COPY . .

EXPOSE 8000
