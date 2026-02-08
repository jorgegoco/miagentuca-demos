FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create tmp directory
RUN mkdir -p .tmp

# Expose port
EXPOSE 8005

# Run the application
CMD ["uvicorn", "orchestration.pipeline_endpoint:app", "--host", "0.0.0.0", "--port", "8005"]
