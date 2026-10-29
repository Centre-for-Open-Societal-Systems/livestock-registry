# Livestock Registry — connector service image.
#
# The crop build of the vendored connector at cropsown-regsitry d0cd4f9, pinned by
# digest. It is the build with the Farmer-reference receiver changes: WebSub content
# envelope, Ed25519 registry-payload signing and mapped-payload validation.
#
# That build also creates crop's four ODK pipelines in whatever connector database it
# starts against (default_pipelines.py, called at every API start). This image swaps that
# module for one that creates nothing. Livestock's connector definitions are
# configuration, created through the connector admin API as the runbooks describe.
#
# Build context = repo root. The connector-as-config work in oan-helm (build from
# OpenG2P/registry-connector) replaces this image.
ARG CONNECTOR_BASE=379220350808.dkr.ecr.ap-south-1.amazonaws.com/gen2/cropsown-registry/connector-service@sha256:198da6ff46db0c4f8ef20550163de78a4833075dbf08d361c5a2905b6bc8ede6
FROM ${CONNECTOR_BASE}

COPY docker/connector-service/default_pipelines.py /tmp/livestock/default_pipelines.py
USER root
RUN python -c "import os, shutil, openg2p_connector_service as p; shutil.copyfile('/tmp/livestock/default_pipelines.py', os.path.join(os.path.dirname(p.__file__), 'default_pipelines.py'))" \
    && rm -rf /tmp/livestock \
    && python -c "import inspect, openg2p_connector_service.default_pipelines as d; assert 'CropSown' not in inspect.getsource(d) and inspect.iscoroutinefunction(d.seed_default_pipelines)"
USER connector
