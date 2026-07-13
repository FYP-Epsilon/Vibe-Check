# Module 03: Equivalence Checking Engine
# ========================================
# Lightweight pure-Python image — no C++ toolchain required.

FROM python:3.10-slim

# Prevent interactive prompts and set Python to unbuffered mode
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install Python dependencies (minimal — no ML/NLP)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and test files
COPY src/ ./src/
COPY tests/ ./tests/

# Expose no ports — this module is a batch processor
# that ingests WIR JSON and outputs verification verdicts.

# Health-check: verify the pipeline module can be imported
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "from src.pipeline import run_pipeline; print('OK')" || exit 1

CMD ["python3", "-m", "src.pipeline"]
