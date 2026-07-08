# syntax=docker/dockerfile:1

# Builds the HTTP entrypoint (src/verbatim/http_api.py) for Cloud Run.
# The CLI (verbatim) isn't the target here -- it needs a local OAuth
# consent flow / token.json that has no meaning inside a container -- so
# this image only ever runs verbatim-server. See docs/workspace-addon-migration.md §6.

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv .venv
COPY --from=builder /app/src src

ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8080

EXPOSE 8080

CMD ["verbatim-server"]
