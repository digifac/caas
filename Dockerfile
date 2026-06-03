# ============================================================
# Stage 1: Builder — compile Python packages (gcc is available)
# ============================================================
FROM python:3.12-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build-only dependencies (gcc for compiling Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from pyproject.toml (without building the project)
# Includes optional dependencies: redis
COPY pyproject.toml .
RUN python -c "import tomllib; \
    data = tomllib.load(open('pyproject.toml', 'rb')); \
    deps = data['project']['dependencies']; \
    extras = data.get('project', {}).get('optional-dependencies', {}); \
    for extra_deps in extras.values(): \
    deps.extend(extra_deps); \
    print('\n'.join(deps))" > requirements.txt \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# Stage 2: Final — runtime image (no gcc!)
# ============================================================
FROM python:3.12-slim AS final

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime system dependencies: Tesseract + all languages
# tesseract-ocr-all bundles every language pack and script data in one package
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr-all \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages from builder
COPY --from=builder /install /usr/local

# Set working directory
WORKDIR /app

# Copy only runtime-needed source (exclude examples/, tests/, docs, etc.)
COPY pyproject.toml .
COPY main.py .
COPY app/ app/

# Create a non-root user and switch to it
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start application with Gunicorn (multiple Uvicorn workers)
# Workers can be tuned via CAAS_WORKERS env var (default: 2)
CMD ["sh", "-c", "gunicorn app.api:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers ${CAAS_WORKERS:-2}"]
