FROM python:3.10-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core build tools and dependencies for SPOT
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    cmake \
    pkg-config \
    wget \
    tar \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Download, build, and install SPOT 2.11.6 from source
WORKDIR /tmp
RUN wget https://www.lrde.epita.fr/dload/spot/spot-2.11.6.tar.gz && \
    tar xzf spot-2.11.6.tar.gz && \
    cd spot-2.11.6 && \
    ./configure --prefix=/usr && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf spot-2.11.6*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
