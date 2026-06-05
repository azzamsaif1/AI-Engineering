FROM python:3.11-slim

WORKDIR /app

# System deps for spaCy, scipy, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models at build time
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download de_core_news_sm

# Copy application code
COPY . .

# Create models cache directory
RUN mkdir -p /app/models_cache

# Expose port
EXPOSE 5001

# Run with gunicorn + eventlet for production websocket support
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", \
     "--bind", "0.0.0.0:5001", "--timeout", "120", "app:app"]
