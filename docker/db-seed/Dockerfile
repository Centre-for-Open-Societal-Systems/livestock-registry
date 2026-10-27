# Native seeding machinery; no database imports, worker or bundle patches.
ARG RP_VERSION=1.2.2-rc.557
FROM openg2p/openg2p-registry-db-seed:${RP_VERSION}
RUN rm -rf /seed/meta_data/* /seed/awe_meta_data/* /seed/templates/* /seed/seed-data/*
COPY livestock-extension/src/openg2p_registry_livestock_extension/meta_data/ /seed/meta_data/
COPY livestock-extension/src/openg2p_registry_livestock_extension/templates/ /seed/templates/
COPY livestock-extension/src/openg2p_registry_livestock_extension/awe_meta_data/ /seed/awe_meta_data/
# The image is the platform's db-seed with the Livestock extension's metadata,
# AWE policies and templates in place of the reference extension's. The native
# entrypoint applies the whole tree (meta_data, awe_meta_data, templates).
ENTRYPOINT ["/seed/entrypoint.sh"]
