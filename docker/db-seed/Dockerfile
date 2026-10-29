# Native seeding machinery; no database imports, worker or bundle patches.
ARG RP_VERSION=1.2.2-rc.557
FROM openg2p/openg2p-registry-db-seed:${RP_VERSION}
RUN rm -rf /seed/meta_data/* /seed/awe_meta_data/* /seed/templates/* /seed/seed-data/*
COPY livestock-extension/src/openg2p_registry_livestock_extension/meta_data/ /seed/meta_data/
COPY livestock-extension/src/openg2p_registry_livestock_extension/templates/ /seed/templates/
COPY livestock-extension/src/openg2p_registry_livestock_extension/awe_meta_data/ /seed/awe_meta_data/
# Reporting layer applied by the chart's lr-reporting-views hook (post-install and
# post-upgrade): the Master Data geography copy and the lr_rpt_* views the
# dashboard API reads. The hook runs these two paths from this image.
COPY docker/db-seed/reporting_views.sql /seed/reporting_views.sql
COPY docker/db-seed/reporting-geo-sync.sh /seed/reporting-geo-sync.sh
RUN chmod +x /seed/reporting-geo-sync.sh
# Sample data (LOAD_SAMPLE_DATA=true). The platform image checks out openg2p-data
# at /openg2p-data; this one checks out the COSS repository at a pinned commit in
# its place, the source of the ETH-OAN pack's sample farmers and their livestock
# (samples/farmer_ids.json, samples/livestock.json).
ARG OPENG2P_DATA_REPO=https://github.com/Centre-for-Open-Societal-Systems/openg2p-data.git
ARG OPENG2P_DATA_REF=5aa26d65aabd979ad96a2fc4a293c8f12de18bf7
RUN rm -rf /openg2p-data && mkdir -p /openg2p-data && cd /openg2p-data \
    && git init -q && git remote add origin ${OPENG2P_DATA_REPO} \
    && git fetch -q --depth 1 origin ${OPENG2P_DATA_REF} && git checkout -q FETCH_HEAD \
    && rm -rf .git
COPY --chmod=755 docker/db-seed/load_sample_data.py /seed/
# The image is the platform's db-seed with the Livestock extension's metadata,
# AWE policies and templates in place of the reference extension's. The native
# entrypoint applies the whole tree (meta_data, awe_meta_data, templates).
ENTRYPOINT ["/seed/entrypoint.sh"]
