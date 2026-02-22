FROM python:3.12-slim
WORKDIR /app

# System dependencies: libmupdf-dev is required by PyMuPDF (fitz) for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for persistent data (will be overridden by Easypanel volume mounts)
RUN mkdir -p /app/chroma_data /app/uploaded_pdfs /app/chunk_images

EXPOSE 8007

# 1. Run preload.py to index medical papers (idempotent — skips if already done)
# 2. Start uvicorn API server
CMD ["sh", "-c", "python scripts/preload.py && uvicorn orchestration.chatbot_endpoint:app --host 0.0.0.0 --port 8007"]
