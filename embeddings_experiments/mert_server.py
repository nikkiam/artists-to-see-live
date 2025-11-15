"""
MERT-v1-95M Inference Server for HuggingFace Endpoints

FastAPI server that loads MERT and processes full 30-second audio clips.
Follows official MERT HuggingFace model card implementation.
"""
import os
from contextlib import asynccontextmanager
from typing import List

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import Wav2Vec2FeatureExtractor, AutoModel

# Global model variables (loaded on startup)
model = None
processor = None
device = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MERT model on startup - follows official HF pattern."""
    global model, processor, device

    try:
        model_id = os.environ.get("MODEL_ID", "m-a-p/MERT-v1-95M")

        print(f"[STARTUP] Loading MERT model: {model_id}")
        print(f"[STARTUP] HF_HOME: {os.environ.get('HF_HOME', 'not set')}")
        print(f"[STARTUP] TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE', 'not set')}")

        # Determine device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[STARTUP] Using device: {device}")
        if torch.cuda.is_available():
            print(f"[STARTUP] CUDA device count: {torch.cuda.device_count()}")
            print(f"[STARTUP] CUDA device name: {torch.cuda.get_device_name(0)}")

        # Load model - official HF pattern
        print(f"[STARTUP] Downloading/loading model from HuggingFace...")
        model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        print(f"[STARTUP] Model loaded, moving to device...")
        model = model.to(device)
        model.eval()
        print(f"[STARTUP] Model ready on {device}")

        # Load processor - official HF pattern
        print(f"[STARTUP] Loading processor...")
        processor = Wav2Vec2FeatureExtractor.from_pretrained(
            model_id,
            trust_remote_code=True
        )

        print(f"[STARTUP] ✓ Model loaded successfully on {device}")
        print(f"[STARTUP] ✓ Processor sampling rate: {processor.sampling_rate}Hz")
        print(f"[STARTUP] ✓ Server ready to accept requests")

        yield

        # Cleanup (if needed)
        print("[SHUTDOWN] Shutting down...")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        raise


# Initialize FastAPI with lifespan
app = FastAPI(title="MERT Inference Server", version="1.0.0", lifespan=lifespan)


class AudioInput(BaseModel):
    """Audio input - expects raw audio samples as list of floats."""
    audio: List[float]
    sampling_rate: int = 24000


class EmbeddingOutput(BaseModel):
    """Embedding output - returns all 13 layers, time-reduced to [13, 768]."""
    embedding: List[List[float]]  # Shape: [13, 768]
    shape: List[int]


@app.get("/health")
async def health():
    """Health check endpoint."""
    if model is None:
        return {"status": "loading", "model": "MERT-v1-95M", "message": "Model is still loading"}
    return {"status": "healthy", "model": "MERT-v1-95M", "device": str(device)}


@app.post("/embed", response_model=EmbeddingOutput)
async def extract_embedding(audio_input: AudioInput):
    """
    Extract MERT embeddings from audio - all 13 layers.

    Follows official HuggingFace implementation pattern.
    Returns [13, 768] - all layers, time-reduced.
    """
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Convert audio list to numpy array
        audio = np.array(audio_input.audio, dtype=np.float32)

        print(f"Received audio: {len(audio)} samples at {audio_input.sampling_rate}Hz")
        print(f"Duration: {len(audio) / audio_input.sampling_rate:.2f}s")

        # Prepare inputs - official HF pattern
        inputs = processor(
            audio,
            sampling_rate=audio_input.sampling_rate,
            return_tensors="pt"
        )

        # Move to device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Extract embeddings - official HF pattern
        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)

        # Official HF pattern: extract all 13 layers
        # Shape: [13 layers, Time steps, 768 features]
        all_layer_hidden_states = torch.stack(outputs.hidden_states).squeeze()

        print(f"All layers shape: {all_layer_hidden_states.shape}")

        # Official HF pattern: time-reduce while preserving layers
        # "for utterance level classification tasks, you can simply reduce the representation in time"
        time_reduced_hidden_states = all_layer_hidden_states.mean(-2)

        print(f"Time-reduced shape: {time_reduced_hidden_states.shape}")  # [13, 768]

        # Convert to numpy
        embedding_np = time_reduced_hidden_states.cpu().numpy()

        return EmbeddingOutput(
            embedding=embedding_np.tolist(),
            shape=list(embedding_np.shape)
        )

    except Exception as e:
        print(f"Error extracting embedding: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "MERT-v1-95M Inference Server",
        "model": "m-a-p/MERT-v1-95M",
        "embedding_shape": "[13, 768]",
        "layers": "All 13 layers (choose empirically for downstream tasks)",
        "max_duration": "30 seconds",
        "endpoints": {
            "health": "/health",
            "embed": "/embed (POST)",
        }
    }
