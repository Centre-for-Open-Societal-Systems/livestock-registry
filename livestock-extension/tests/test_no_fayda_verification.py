"""Livestock identifies the farmer by Farmer ID and a typed Fayda ID; no eSignet verification."""

import importlib
from pathlib import Path

PACKAGE = "openg2p_registry_livestock_extension"
META = Path(importlib.import_module(PACKAGE).__file__).parent / "meta_data"
CLEANUP = "zz-oan/92_remove_fayda_verification.sql"


def seed_files():
    return sorted(
        str(path.relative_to(META)).replace("\\", "/") for path in META.rglob("*.sql")
    )


def test_cleanup_runs_after_every_register_metadata_file():
    files = seed_files()
    cleanup = files.index(CLEANUP)
    assert all(
        index < cleanup
        for index, name in enumerate(files)
        if name.startswith("register-metadata/")
    )


def test_no_seed_adds_the_verification_widget():
    for name in seed_files():
        if name == CLEANUP:
            continue
        text = (META / name).read_text(encoding="utf-8")
        assert "oan-identity-verification" not in text, name
        assert "requires_registrant_authentication=true" not in text, name


def test_cleanup_removes_the_widget_and_the_authentication_flag():
    text = (META / CLEANUP).read_text(encoding="utf-8")
    assert "oan-identity-verification" in text
    assert "requires_registrant_authentication = false" in text


def test_the_verification_modules_are_gone():
    root = Path(importlib.import_module(PACKAGE).__file__).parent
    assert not (root / "controllers").exists()
    assert not (
        root / "register_domain" / "services" / "identity_verification.py"
    ).exists()
    assert not (root / "register_domain" / "identity_claims.py").exists()
