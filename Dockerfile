# --- Stage 1: Builder ---
FROM python:3.10-slim as builder

# Set work directory
WORKDIR /app

# Install system build dependencies (needed for some python packages)
RUN apt-get update && apt-get install -y build-essential

# Copy requirements and install them into a specific folder (/install)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Copy the installed libraries from the Builder stage
COPY --from=builder /install /usr/local

# Copy our application code
COPY app /app/app

# Create a directory for the database (Volume mount point)
RUN mkdir -p /data

# Set environment variables
# Python won't buffer output (so logs show up immediately)
ENV PYTHONUNBUFFERED=1
# Tell our app where the DB lives by default
ENV DATABASE_URL="sqlite:////data/app.db"

# Expose the port
EXPOSE 8000

# The command to run when the container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]