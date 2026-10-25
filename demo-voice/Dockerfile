FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8010

# Run the application (single worker: the rate limiter keeps its counters in memory)
CMD ["uvicorn", "orchestration.token_endpoint:app", "--host", "0.0.0.0", "--port", "8010"]
