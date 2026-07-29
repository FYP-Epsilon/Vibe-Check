FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core build tools and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    cmake \
    pkg-config \
    python3-dev \
    python3-pip \
    pybind11-dev \
    nlohmann-json3-dev \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Download, build, and install SPOT 2.11.6 from source
# Disabling python bindings for SPOT itself as we use our own Pybind11 bridge
WORKDIR /tmp
RUN wget https://www.lrde.epita.fr/dload/spot/spot-2.11.6.tar.gz && \
    tar xzf spot-2.11.6.tar.gz && \
    cd spot-2.11.6 && \
    ./configure --prefix=/usr --disable-python && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf spot-2.11.6*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project files
COPY CMakeLists.txt .
COPY src/ ./src/

# Execute CMake build to generate the 'vibecheck_lifter' shared library
RUN mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc)

# Ensure the library is in the python path
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
