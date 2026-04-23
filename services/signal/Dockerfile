# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the signal service.
#   - builder: installs the package + all runtime deps into a prefix.
#   - runtime: copies only the installed prefix, drops to a non-root user.
# Non-root USER works for local docker-compose. On OpenShift the restricted
# SCC re-assigns UID per namespace; files under /usr/local are world-
# readable, so that reassignment is fine.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY pyproject.toml ./
COPY src/ src/

RUN pip install --prefix=/install .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user + group. UID is ignored by OpenShift restricted SCC but
# honored elsewhere.
RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --home /app --shell /sbin/nologin app

WORKDIR /app

COPY --from=builder /install /usr/local

USER app

EXPOSE 8001

CMD ["uvicorn", "nexusquant_signal.main:app", "--host", "0.0.0.0", "--port", "8001"]
