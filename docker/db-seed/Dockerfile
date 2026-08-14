# Livestock Registry — DB-seed image.
#
# Thin extension of the registry-platform db-seed base image. The base ships all
# the generic seeding MACHINERY (entrypoint.sh, load/upload scripts, the shared
# openg2p-data clone). This image adds ONLY livestock's seed content: the SQL
# metadata, AWE metadata and Jinja templates carried by the livestock-extension,
# plus the livestock sub-table sample JSON. The entrypoint (inherited) reads
# /seed/* at container-run time; behaviour is toggled entirely via env from the
# Helm Job.
#
# Build context = repo root (so livestock-extension/ and docker/db-seed/ are both
# reachable).
ARG RP_VERSION=0.0.0-develop.296
FROM openg2p/openg2p-registry-db-seed:${RP_VERSION}

# The RP db-seed image ships the reference registry's seed; clear it so only
# livestock's seed is applied.
RUN rm -rf /seed/meta_data/* /seed/awe_meta_data/* /seed/templates/* /seed/seed-data/*

COPY livestock-extension/src/openg2p_registry_livestock_extension/meta_data/     /seed/meta_data/
COPY livestock-extension/src/openg2p_registry_livestock_extension/awe_meta_data/ /seed/awe_meta_data/
COPY livestock-extension/src/openg2p_registry_livestock_extension/templates/     /seed/templates/
COPY docker/db-seed/sample-data/                                               /seed/sample-data/
