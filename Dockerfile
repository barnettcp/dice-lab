# =============================================================================
# DiceLab Multi-Stage Dockerfile
#
# Builds all five language implementations and packages them with the Python
# benchmark runner and analysis pipeline into a single image.
#
# Usage:
#   docker build -t dice-lab .
#   docker run dice-lab
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: C++ builder
# ---------------------------------------------------------------------------
FROM gcc:14 AS cpp-builder
WORKDIR /build
COPY implementations/cpp/src/ src/
RUN g++ -std=c++17 -O3 -o dice-lab src/main.cpp src/Dice.cpp

# ---------------------------------------------------------------------------
# Stage 2: Rust builder
# ---------------------------------------------------------------------------
FROM rust:1.86 AS rust-builder
WORKDIR /build
COPY implementations/rust/Cargo.toml .
COPY implementations/rust/src/ src/
RUN cargo build --release

# ---------------------------------------------------------------------------
# Stage 3: Go builder
# ---------------------------------------------------------------------------
FROM golang:1.24 AS go-builder
WORKDIR /build
COPY implementations/go/go.mod .
COPY implementations/go/main.go .
RUN CGO_ENABLED=0 go build -o dice-lab .

# ---------------------------------------------------------------------------
# Stage 4: Java builder
# ---------------------------------------------------------------------------
FROM eclipse-temurin:21-jdk AS java-builder
WORKDIR /build
COPY implementations/java/src/ src/
RUN mkdir -p out && javac -d out src/DiceLab.java

# ---------------------------------------------------------------------------
# Stage 5: Final runtime image
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS final

# Install a headless JRE for running compiled Java bytecode.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for the benchmark runner and analysis pipeline.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy built binaries into the paths the benchmark runner expects -------

# C++: implementations/cpp/dice-lab
COPY --from=cpp-builder /build/dice-lab implementations/cpp/dice-lab

# Rust: implementations/rust/target/release/dice-lab
COPY --from=rust-builder /build/target/release/dice-lab implementations/rust/target/release/dice-lab

# Go: implementations/go/dice-lab
COPY --from=go-builder /build/dice-lab implementations/go/dice-lab

# Java: implementations/java/out/DiceLab.class
COPY --from=java-builder /build/out/ implementations/java/out/

# --- Copy source / scripts ------------------------------------------------

# Python implementation (runs from source)
COPY implementations/python/ implementations/python/

# Benchmark runner
COPY benchmarks/ benchmarks/

# Analysis pipeline + templates + assets
COPY analysis/ analysis/

# Store report assets in a separate location so they survive volume mounts
# on /app/reports.  The CMD copies them into place before the pipeline runs.
COPY reports/assets/ /opt/dice-lab-assets/

# Ensure output directories exist
RUN mkdir -p shared-data reports benchmarks/results

# --- Default entry point ---------------------------------------------------
# 1. Restore report assets into the (possibly mounted) reports directory.
# 2. Run benchmarks across all languages.
# 3. Run the analysis pipeline to produce CSVs and the HTML report.
CMD ["sh", "-c", "\
  cp -r /opt/dice-lab-assets reports/assets \
  && python benchmarks/benchmark_runner.py \
    --languages python cpp rust go java \
    --output benchmarks/results/benchmark_report.json \
  && python analysis/run_analytic_pipeline.py \
"]
