# Multi-stage Dockerfile for AstroRemedis Backend
# Optimized for AWS deployment (ECS, App Runner, Elastic Beanstalk)

# Stage 1: Build stage (if needed for any build steps)
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY backend/ ./backend/
COPY wsgi.py .
COPY Procfile .

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=wsgi:application

# Switch to non-root user
USER appuser

# Expose port (AWS will map this)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# Use Gunicorn as WSGI server
CMD ["gunicorn", "wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "2", "--worker-class", "sync", "--access-logfile", "-", "--error-logfile", "-"]

