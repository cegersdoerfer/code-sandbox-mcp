FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create workspace directory
RUN mkdir -p /workspace

# Copy application code
COPY kernel_service.py .
COPY jupyter_imports.py .

# Expose port
ARG CONTAINER_SERVICE_PORT=8060
EXPOSE ${CONTAINER_SERVICE_PORT}

# Run the service
CMD ["python", "kernel_service.py"] 