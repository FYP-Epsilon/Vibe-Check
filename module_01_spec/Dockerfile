FROM python:3.10-slim

# Module 01 never imports SPOT (Python bindings or the C++ library) at
# runtime -- formula_normalizer.py only produces SPOT-*compatible* string
# syntax for Module 03 to later parse in its own container, and that
# module isn't even wired into the real pipeline (never imported by
# api.py/main.py). Real SPOT model checking runs in module_03_equiv's own
# container via the compiled vibecheck_lifter C++ engine. Building SPOT
# from source here (previously several minutes per build) was pure dead
# weight left over from an earlier design (see Next Steps.md item #11).

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
