# Livestock Registry — Celery image (workers + beat).
#
# Thin extension of the registry-platform celery base image (see
# docker/staff-api/Dockerfile for the full rationale). Adds only the
# livestock domain model; both celery packages, the run_celery.py wrapper, the
# CELERY_* ENV defaults and the CMD are inherited from the base. A single image
# runs as worker or beat, selected at runtime via CELERY_APP.
#
# Build context = repo root (so livestock-extension/ is reachable).
ARG RP_VERSION=0.0.0-develop.296
FROM openg2p/openg2p-registry-celery:${RP_VERSION}

# Option C: select livestock's domain model (coexists with the base image's
# reference extension; env picks livestock, no uninstall needed).
ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_livestock_extension

COPY livestock-extension/ /app/livestock-extension/
RUN pip install --no-cache-dir /app/livestock-extension
