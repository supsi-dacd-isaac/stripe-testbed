# =============================================================================
# FEDECOM Stripe Demo — Docker Build
# =============================================================================
# Multi-stage build:
#   Stage 1 (builder): Compile the Rust CLI binary
#   Stage 2 (runtime): Python + Flask with the pre-compiled binary
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build the Rust CLI
# -----------------------------------------------------------------------------
FROM rust:1.83-bookworm AS builder

WORKDIR /build

# Copy Rust project files
COPY rust/Cargo.toml rust/Cargo.lock ./rust/
COPY rust/src ./rust/src

# Build release binary
WORKDIR /build/rust
RUN cargo build --release

# -----------------------------------------------------------------------------
# Stage 2: Python runtime with Flask
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the compiled Rust binary from builder stage
COPY --from=builder /build/rust/target/release/stripe-testbed /app/rust/target/release/stripe-testbed

# Copy Python dependencies and install
COPY python/requirements.txt /app/python/requirements.txt
RUN pip install --no-cache-dir -r /app/python/requirements.txt

# Copy web application code
COPY web/__init__.py /app/web/
COPY web/app.py /app/web/
COPY web/runner.py /app/web/
COPY web/templates /app/web/templates
COPY web/static /app/web/static

# Create directories for config (will be mounted at runtime)
RUN mkdir -p /app/rust/conf

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=web.app
ENV STRIPE_TESTBED_BIN=/app/rust/target/release/stripe-testbed

# Switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Run Flask development server (use gunicorn in production)
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]

