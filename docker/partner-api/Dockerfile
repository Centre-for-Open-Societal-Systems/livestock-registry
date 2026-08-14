# Livestock Registry — Partner API image.
#
# Thin extension of the registry-platform base image (see
# docker/staff-api/Dockerfile for the full rationale). Adds only the
# livestock domain model; ENV defaults and the migrate+gunicorn CMD are inherited.
#
# Build context = repo root (so livestock-extension/ is reachable).
ARG RP_VERSION=0.0.0-develop.296
FROM openg2p/openg2p-registry-partner-api:${RP_VERSION}

# Option C: select livestock's domain model (coexists with the base image's
# reference extension; env picks livestock, no uninstall needed).
ENV REGISTRY_EXTENSION_MODULE=openg2p_registry_livestock_extension

COPY livestock-extension/ /app/livestock-extension/
RUN pip install --no-cache-dir /app/livestock-extension
