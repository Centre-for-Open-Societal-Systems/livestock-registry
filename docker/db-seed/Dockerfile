# Native seeding machinery; no database imports, worker or bundle patches.
ARG RP_VERSION=1.2.2-rc.614
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
# Schema and data migrations for databases created before the models gained
# a column (never seed configuration). The chart's lr-schema-migrations hook
# runs apply-migrations.sh, which applies each file once.
COPY docker/db-seed/migrations/ /seed/migrations/
COPY --chmod=755 docker/db-seed/apply-migrations.sh /seed/apply-migrations.sh
# openg2p-data: the COSS repository at a pinned commit, checked out at
# /openg2p-data in place of the platform's copy. It is the only source of seed
# data in this image: the ETH-OAN pack's sample people and their livestock
# (samples/individuals.json, samples/livestock.json, LOAD_SAMPLE_DATA=true) and
# the OAN staff-portal theme (themes/oan_theme: palette and background image).
ARG OPENG2P_DATA_REPO=https://github.com/Centre-for-Open-Societal-Systems/openg2p-data.git
ARG OPENG2P_DATA_REF=5a8291769a395c78ea5b6625513a7f951595a51f
RUN rm -rf /openg2p-data && mkdir -p /openg2p-data && cd /openg2p-data     && git init -q && git remote add origin ${OPENG2P_DATA_REPO}     && git fetch -q --depth 1 origin ${OPENG2P_DATA_REF} && git checkout -q FETCH_HEAD     && rm -rf .git
COPY --chmod=755 docker/db-seed/load_sample_data.py /seed/
# The image is the platform's db-seed with the Livestock extension's metadata,
# AWE policies and templates in place of the reference extension's. The native
# entrypoint applies the whole tree (meta_data, awe_meta_data, templates).
# Render this registry's oan_theme entry into the seed tree. It sorts after the
# registry configuration (registry-configurations/g2p_registry_configuration.sql,
# which inserts the row with the factory theme) and points that row at oan_theme;
# the factory theme row stays as seeded (DO NOTHING).
RUN mkdir -p /seed/meta_data/zz-oan  && python3 /openg2p-data/scripts/themes/build_theme_sql.py livestock > /seed/meta_data/zz-oan/90_oan_theme.sql
ENTRYPOINT ["/seed/entrypoint.sh"]
