# Use Python 3.13 slim image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

#install gdal
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils libproj-dev gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .
RUN chmod +x entrypoint.sh

# Collect static files
ENV DJANGO_SETTINGS_MODULE=snorkelmap.production
RUN python manage.py collectstatic --noinput

# Expose port (Dokploy will use $PORT env variable)
EXPOSE 8000

# entrypoint.sh applies migrations, then execs gunicorn. Runs on every
# container start, i.e. every deploy Dokploy triggers from a GitHub push.
ENTRYPOINT ["./entrypoint.sh"]