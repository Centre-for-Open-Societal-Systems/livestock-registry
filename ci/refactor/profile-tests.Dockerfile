# Test-only dependencies; the production images inherit unmodified runtimes.
FROM openg2p/openg2p-registry-staff-api:1.2.2-rc.614
RUN pip install --no-cache-dir aiosqlite==0.21.0 pytest==8.4.2 ruff==0.17.2
