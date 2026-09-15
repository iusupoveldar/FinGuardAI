FROM python:3.12-slim

# Hugging Face Docker Spaces run as UID 1000. Building as the same user keeps
# the application files, model cache, and generated Chroma index accessible.
RUN useradd --create-home --uid 1000 user

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /home/user/app

# Install a CPU-only PyTorch build so the CPU Basic image does not contain
# unused CUDA libraries.
COPY --chown=user:user backend/requirements-runtime.txt backend/requirements-runtime.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu torch && \
    python -m pip install -r backend/requirements-runtime.txt

# Persistent customer and transaction data remains in Neon. Only API and policy
# retrieval code is needed in the hosted image.
COPY --chown=user:user pyproject.toml pyproject.toml
COPY --chown=user:user backend/app backend/app
COPY --chown=user:user backend/main.py backend/main.py
COPY --chown=user:user ai ai

# Build the small policy index and cache MiniLM in the immutable image. Never
# train the 1.32-million-row risk model during a deployment build.
RUN python -m pip install --editable . --no-deps && \
    python -m ai.ingestion

# Retrieval is self-contained at runtime: the model and policy index were
# downloaded and built in the preceding image layer.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /home/user/app/backend

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=4)"

# One worker intentionally owns one cached embedding model. Multiple workers
# would duplicate PyTorch and model memory.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
