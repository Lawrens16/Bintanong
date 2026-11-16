# Hosted-LLM agent API (Phase 13 fork). No GPU, local model, encoder or torch.
# SWI-Prolog comes from the official image (same 10.0.2 as docker/api.Dockerfile builds from source);
# uv installs Python 3.13 on top, so Prolog and Python share one set of system libraries.
ARG SWIPL_IMAGE=swipl:10.0.2

FROM ${SWIPL_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
# janus-swi has no Linux wheel; it compiles here against this image's SWI-Prolog.
RUN uv python install 3.13 && uv sync --frozen --no-dev --extra api --python 3.13

FROM ${SWIPL_IMAGE} AS runtime
COPY --from=build /opt/python /opt/python
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY knowledge /app/knowledge
COPY backend /app/backend
RUN useradd --create-home --uid 10001 bintanong
USER bintanong
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1 PORT=10000
EXPOSE 10000
# One process: sessions live in memory, and Render free has 512 MB.
CMD ["sh", "-c", "exec uvicorn --factory backend.bintanong_api.agent_app:load_agent_app --host 0.0.0.0 --port \"$PORT\" --workers 1"]
