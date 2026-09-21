# Document AI Pilot UI
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PILOT_HOST=0.0.0.0 \
    PILOT_PORT=8765

# System deps (python-docx / lxml often need none on slim wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY data/user_scenarios ./data/user_scenarios

RUN pip install --upgrade pip \
    && pip install -e ".[ui]"

# Pilot runs written here (compose can mount a volume)
RUN mkdir -p data/user_scenarios/_pilot

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PILOT_PORT}/api/pilot/health" || exit 1

CMD ["python", "scripts/run_pilot_ui.py", "--host", "0.0.0.0", "--port", "8765"]
