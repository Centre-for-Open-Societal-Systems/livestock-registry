# Test-only dependencies; the production images inherit unmodified runtimes.
FROM openg2p/openg2p-registry-staff-api:1.2.2-rc.557
RUN pip install --no-cache-dir aiosqlite==0.21.0
