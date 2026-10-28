"""The chart's reporting hook executes two files from the db-seed image."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_db_seed_image_carries_the_reporting_files():
    dockerfile = (ROOT / "docker/db-seed/Dockerfile").read_text(encoding="utf-8")
    for name in ("reporting_views.sql", "reporting-geo-sync.sh"):
        assert (ROOT / "docker/db-seed" / name).is_file(), name
        assert f"COPY docker/db-seed/{name} /seed/{name}" in dockerfile, name
    assert "chmod +x /seed/reporting-geo-sync.sh" in dockerfile
    assert 'ENTRYPOINT ["/seed/entrypoint.sh"]' in dockerfile


def test_reporting_views_are_reapplicable():
    sql = (ROOT / "docker/db-seed/reporting_views.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS lr_rpt_geo" in sql
    for view in ("lr_rpt_animal", "lr_rpt_holding"):
        assert f"DROP MATERIALIZED VIEW IF EXISTS {view}" in sql
