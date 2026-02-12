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

# Create tmp directory and ChromaDB data directory
RUN mkdir -p .tmp
RUN mkdir -p /app/chroma_data

# Expose port
EXPOSE 8006

# Run the application
CMD ["uvicorn", "orchestration.rag_endpoint:app", "--host", "0.0.0.0", "--port", "8006"]
