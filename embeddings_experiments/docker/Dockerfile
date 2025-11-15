# Dockerfile for MERT-v1-95M Inference Server
# Optimized for HuggingFace Spaces

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set cache environment variables BEFORE installing packages
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface/transformers
ENV HF_DATASETS_CACHE=/tmp/huggingface/datasets
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
RUN pip install --no-cache-dir \
    transformers==4.57.1 \
    torch==2.6.0 \
    torchaudio==2.6.0 \
    librosa==0.10.1 \
    numpy==1.26.4 \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.9.2

# Copy server file
COPY mert_server.py /app/server.py

# Set model environment variable
ENV MODEL_ID=m-a-p/MERT-v1-95M

# Expose port (configurable via PORT env var, defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Health check (give 5 minutes for model download on first start)
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run server (port configurable via $PORT environment variable)
CMD sh -c "uvicorn server:app --host 0.0.0.0 --port ${PORT}"
