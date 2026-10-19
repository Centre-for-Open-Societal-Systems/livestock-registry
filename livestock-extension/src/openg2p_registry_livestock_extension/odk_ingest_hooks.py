"""ODK Ingestion Hooks for OpenG2P Livestock Registry.

Intercepts ingestion requests, ensures database connections, transforms ODK Central payloads,
wraps payloads into OpenG2P standard envelopes, and ensures complete storage into
both Intake Forms and primary Livestock Registry tables without datetime serialization errors.
"""
import importlib
import json
import logging
import os
import sys
import uuid
from datetime import date, datetime
from jinja2 import Template

# Alias openg2p_registry_extensions so Celery worker / platform packages can import extension settings
try:
    import openg2p_registry_livestock_extension
    sys.modules["openg2p_registry_extensions"] = openg2p_registry_livestock_extension
    import openg2p_registry_livestock_extension.config
    sys.modules["openg2p_registry_extensions.config"] = openg2p_registry_livestock_extension.config
    import openg2p_registry_livestock_extension.register_domain
    sys.modules["openg2p_registry_extensions.register_domain"] = openg2p_registry_livestock_extension.register_domain
except Exception:
    pass

try:
    from openg2p_registry_core.helpers.template_helper import TemplateHelper
    if TemplateHelper.get_component() is None:
        TemplateHelper()
except Exception:
    pass

_logger = logging.getLogger("openg2p.odk_ingest_hooks")


def _full_name(*parts) -> str | None:
    """Join the non-blank name parts; None when there are none. A missing part
    used to be formatted in as the text "None" ("None None None")."""
    name = " ".join(str(p).strip() for p in parts if p is not None and str(p).strip() and str(p).strip() != "None")
    return name or None


def _make_json_serializable(obj):
    """Recursively convert dates/datetimes to ISO strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


_GEO_LABEL_CACHE = {
    "central_ethiopia": "Central Ethiopia",
    "amhara": "Amhara",
    "dire": "Dire Dawa",
    "dire_dawa": "Dire Dawa",
    "oromia": "Oromia",
    "benishangul": "Benishangul-Gumuz",
    "ethiopia_somali": "Somali",
    "somali": "Somali",
    "tigray": "Tigray",
    "afar": "Afar",
    "sidama": "Sidama",
    "south_ethiopian": "South Ethiopian",
    "south_west_ethiopia": "South West Ethiopia",
    "gambela": "Gambela",
    "harari": "Harari",
    "addis_ababa": "Addis Ababa",
    "region-ET01": "Tigray",
    "region-ET02": "Afar",
    "region-ET03": "Amhara",
    "region-ET04": "Oromia",
    "region-ET05": "Somali",
    "region-ET06": "Benishangul-Gumuz",
    "region-ET07": "Central Ethiopia",
    "region-ET08": "South Ethiopian",
    "region-ET11": "South West Ethiopia",
    "region-ET12": "Gambela",
    "region-ET13": "Harari",
    "region-ET14": "Addis Ababa",
    "region-ET15": "Dire Dawa",
    "region-ET16": "Sidama",
    "ET01": "Tigray",
    "ET02": "Afar",
    "ET03": "Amhara",
    "ET04": "Oromia",
    "ET05": "Somali",
    "ET06": "Benishangul-Gumuz",
    "ET07": "Central Ethiopia",
    "ET08": "South Ethiopian",
    "ET11": "South West Ethiopia",
    "ET12": "Gambela",
    "ET13": "Harari",
    "ET14": "Addis Ababa",
    "ET15": "Dire Dawa",
    "ET16": "Sidama",
}


async def resolve_geo_label(code: str | None, level_prefix: str = "") -> str | None:
    """Resolve an administrative code or mnemonic to its display name, from
    Master Data (the platform reads geography over the Master Data API since
    registry-platform 1.2; there is no Master Data database connection)."""
    if not code:
        return None
    code_str = str(code).strip()
    if not code_str:
        return None
    if code_str in _GEO_LABEL_CACHE:
        return _GEO_LABEL_CACHE[code_str]

    try:
        from . import master_data_lists

        # The form's location CSVs carry the Master Data id without its
        # level prefix and, for kebeles, without the leading "ET0"
        # (kebele_odk.csv 10101101001 is kebele-ET010101101001; a
        # 12-digit code 100101101001 is kebele-ET100101101001). Exact
        # candidates are tried first and on their own: the suffix match
        # below is only a last resort, because 147 of the form's kebele
        # codes end the same as a kebele of another region (ET02... vs
        # ET12...) and an ambiguous suffix match is refused.
        exact = [
            code_str,
            f"{level_prefix}-{code_str}" if level_prefix else code_str,
            f"{level_prefix}-ET{code_str}" if level_prefix else code_str,
            f"{level_prefix}-ET0{code_str}" if level_prefix else code_str,
            f"zone-{code_str}",
            f"woreda-{code_str}",
            f"kebele-{code_str}",
            f"region-{code_str}",
        ]
        label = None
        for candidate in dict.fromkeys(exact):
            label = await master_data_lists.geo_label(candidate)
            if label:
                break
        if not label:
            label = await master_data_lists.geo_label_by_suffix(code_str)
        if label:
            _GEO_LABEL_CACHE[code_str] = label
            return label
    except Exception as e:
        _logger.warning("ODK Hook: Geo resolution error for %s: %s", code_str, e)

    cleaned = code_str.replace("_", " ").title() if "_" in code_str else code_str
    _GEO_LABEL_CACHE[code_str] = cleaned
    return cleaned


def _calc_age_str(dob_val) -> str | None:
    """Calculate age string ('X years, Y months') from date of birth."""
    if not dob_val:
        return None
    try:
        from datetime import date, datetime

        if isinstance(dob_val, str):
            dob = datetime.fromisoformat(dob_val.replace("Z", "")).date()
        elif isinstance(dob_val, date):
            dob = dob_val
        else:
            return None
        today = date.today()
        years = today.year - dob.year
        months = today.month - dob.month
        if today.day < dob.day:
            months -= 1
        if months < 0:
            years -= 1
            months += 12
        if years < 0:
            return None
        return f"{years} years, {months} months"
    except Exception:
        return None


_SPECIES_CANONICAL_MAP = {
    "cattle": "LIVESTOCK_SPECIES_CATTLE",
    "cow": "LIVESTOCK_SPECIES_CATTLE",
    "bovine": "LIVESTOCK_SPECIES_CATTLE",
    "sheep": "LIVESTOCK_SPECIES_SHEEP",
    "ovine": "LIVESTOCK_SPECIES_SHEEP",
    "goat": "LIVESTOCK_SPECIES_GOAT",
    "caprine": "LIVESTOCK_SPECIES_GOAT",
    "camel": "LIVESTOCK_SPECIES_CAMEL",
    "donkey": "LIVESTOCK_SPECIES_DONKEY",
    "horse": "LIVESTOCK_SPECIES_HORSE",
    "mule": "LIVESTOCK_SPECIES_MULE",
    "poultry": "LIVESTOCK_SPECIES_POULTRY",
    "chicken": "LIVESTOCK_SPECIES_POULTRY",
    "pig": "LIVESTOCK_SPECIES_PIG",
    "swine": "LIVESTOCK_SPECIES_PIG",
    "beehive": "LIVESTOCK_SPECIES_BEEHIVE",
    "bee": "LIVESTOCK_SPECIES_BEEHIVE",
}

_VALID_SPECIES_SET = {
    "LIVESTOCK_SPECIES_CATTLE",
    "LIVESTOCK_SPECIES_SHEEP",
    "LIVESTOCK_SPECIES_GOAT",
    "LIVESTOCK_SPECIES_CAMEL",
    "LIVESTOCK_SPECIES_DONKEY",
    "LIVESTOCK_SPECIES_HORSE",
    "LIVESTOCK_SPECIES_MULE",
    "LIVESTOCK_SPECIES_POULTRY",
    "LIVESTOCK_SPECIES_PIG",
    "LIVESTOCK_SPECIES_BEEHIVE",
}


def normalize_species(val: str | None) -> str | None:
    """Normalize a raw species string into canonical OpenG2P attribute value_id.

    A missing species stays None and an unrecognised one comes back as given,
    so the registry's own checks refuse the record (species is required, and
    must be a value of LIVESTOCK_SPECIES). Both used to become Cattle, which
    stored a wrong species without a word."""
    if val is None or not str(val).strip():
        return None
    s = str(val).strip()
    if s.upper() in _VALID_SPECIES_SET:
        return s.upper()
    s_low = s.lower()
    if s_low in _SPECIES_CANONICAL_MAP:
        return _SPECIES_CANONICAL_MAP[s_low]
    if s_low.startswith("livestock_species_"):
        cand = s_low.upper()
        if cand in _VALID_SPECIES_SET:
            return cand
        cand_sub = cand.replace("LIVESTOCK_SPECIES_", "").lower()
        if cand_sub in _SPECIES_CANONICAL_MAP:
            return _SPECIES_CANONICAL_MAP[cand_sub]
    for k, v in _SPECIES_CANONICAL_MAP.items():
        if k in s_low:
            return v
    return s


# The ODK form's breed choices (choices sheet, list `breed`, filtered by
# species) and the LIVESTOCK_BREED value each one stands for. Only these
# names are translated: anything else is passed through unchanged so the
# registry's breed check rejects it with a message, instead of being
# relabelled to some breed of that species. Keep in step with
# odk/livestock_registry.xlsx and the code list (see odk/test_transform.py).
_ODK_BREED_CHOICES = {
    "cattle": {
        "boran": "LIVESTOCK_BREED_BORAN",
        "fogera": "LIVESTOCK_BREED_FOGERA",
        "horro": "LIVESTOCK_BREED_HORRO",
        "sheko": "LIVESTOCK_BREED_SHEKO",
        "begait": "LIVESTOCK_BREED_BEGAIT",
        "arsi": "LIVESTOCK_BREED_ARSI",
        "barka": "LIVESTOCK_BREED_BARKA",
        "local_zebu": "LIVESTOCK_BREED_LOCAL_ZEBU",
        "holstein_friesian_cross": "LIVESTOCK_BREED_HOLSTEIN_CROSS",
        "jersey_cross": "LIVESTOCK_BREED_JERSEY_CROSS",
    },
    "sheep": {
        "menz": "LIVESTOCK_BREED_MENZ",
        "afar": "LIVESTOCK_BREED_AFAR_SHEEP",
        "blackhead_somali": "LIVESTOCK_BREED_BLACKHEAD_SOMALI",
        "horro": "LIVESTOCK_BREED_HORRO_SHEEP",
        "bonga": "LIVESTOCK_BREED_BONGA",
        "washera": "LIVESTOCK_BREED_WASHERA",
        "dorper_cross": "LIVESTOCK_BREED_DORPER_CROSS",
        "local": "LIVESTOCK_BREED_LOCAL_SHEEP",
    },
    "goat": {
        "afar": "LIVESTOCK_BREED_AFAR_GOAT",
        "abergele": "LIVESTOCK_BREED_ABERGELLE",
        "begait": "LIVESTOCK_BREED_BEGAIT_GOAT",
        "central_highland": "LIVESTOCK_BREED_CENTRAL_HIGHLAND",
        "long_eared_somali": "LIVESTOCK_BREED_LONG_EARED_SOMALI",
        "woito_guji": "LIVESTOCK_BREED_WOITO_GUJI",
        "boer_cross": "LIVESTOCK_BREED_BOER_CROSS",
        "local": "LIVESTOCK_BREED_LOCAL_GOAT",
    },
    "camel": {
        "somali": "LIVESTOCK_BREED_SOMALI_CAMEL",
        "afar": "LIVESTOCK_BREED_AFAR_CAMEL",
        "local": "LIVESTOCK_BREED_LOCAL_CAMEL",
    },
    "donkey": {
        "abyssinian": "LIVESTOCK_BREED_ABYSSINIAN_DONKEY",
        "sinnar": "LIVESTOCK_BREED_SINNAR",
        "local": "LIVESTOCK_BREED_LOCAL_DONKEY",
    },
    "horse": {
        "abyssinian": "LIVESTOCK_BREED_ABYSSINIAN_HORSE",
        "oromo": "LIVESTOCK_BREED_OROMO_HORSE",
        "local": "LIVESTOCK_BREED_LOCAL_HORSE",
    },
    "mule": {
        "local": "LIVESTOCK_BREED_LOCAL_MULE",
    },
    "poultry": {
        "bovans_brown": "LIVESTOCK_BREED_BOVANS_BROWN",
        "isa_brown": "LIVESTOCK_BREED_ISA_BROWN",
        "sasso": "LIVESTOCK_BREED_SASSO",
        "koekoek": "LIVESTOCK_BREED_KOEKOEK",
        "white_leghorn_cross": "LIVESTOCK_BREED_WHITE_LEGHORN_CROSS",
        "local_chicken": "LIVESTOCK_BREED_LOCAL_CHICKEN",
    },
    "pig": {
        "large_white": "LIVESTOCK_BREED_LARGE_WHITE",
        "landrace": "LIVESTOCK_BREED_LANDRACE",
        "local": "LIVESTOCK_BREED_LOCAL_PIG",
    },
    "beehive": {
        "apis_mellifera_scutellata": "LIVESTOCK_BREED_APIS_MELLIFERA",
    },
}


def normalize_breed(breed_val: str | None, species_val: str | None = None) -> str | None:
    """Translate an ODK breed choice into its LIVESTOCK_BREED value id.

    A value id is returned as is. A form choice name is looked up for the
    animal's species. Anything else (a breed of another species, a typo, a
    list the form gained without this map) comes back unchanged, so domain
    validation rejects the submission rather than the registry storing a
    different breed than the one recorded in the field.
    """
    if not breed_val:
        return None
    b = str(breed_val).strip()
    if b.upper().startswith("LIVESTOCK_BREED_"):
        return b.upper()
    sp = normalize_species(species_val) if species_val else None
    species_key = (sp or "").replace("LIVESTOCK_SPECIES_", "").lower()
    return _ODK_BREED_CHOICES.get(species_key, {}).get(b.lower(), b)


def normalize_vaccine(vaccine_val: str | None, species_val: str | None = None) -> str:
    """Normalize a raw vaccine string into canonical OpenG2P attribute value_id based on species."""
    if not vaccine_val:
        return "ROUTINE"
    v = str(vaccine_val).strip()
    if v.upper().startswith("VACCINE_TYPE_"):
        return v.upper()
    v_low = v.lower()
    sp = normalize_species(species_val) if species_val else None

    if "bovine_pasteurellosis" in v_low:
        return "VACCINE_TYPE_PASTEURELLOSIS_CATTLE"
    if "caprine_pasteurellosis" in v_low:
        return "VACCINE_TYPE_PASTEURELLOSIS_GOAT"
    if "ovine_pasteurellosis" in v_low:
        return "VACCINE_TYPE_PASTEURELLOSIS_SHEEP"
    if "camel_pasteurellosis" in v_low:
        return "VACCINE_TYPE_PASTEURELLOSIS_CAMEL"
    if "pasteurellosis" in v_low:
        if sp == "LIVESTOCK_SPECIES_GOAT":
            return "VACCINE_TYPE_PASTEURELLOSIS_GOAT"
        if sp == "LIVESTOCK_SPECIES_SHEEP":
            return "VACCINE_TYPE_PASTEURELLOSIS_SHEEP"
        if sp == "LIVESTOCK_SPECIES_CAMEL":
            return "VACCINE_TYPE_PASTEURELLOSIS_CAMEL"
        return "VACCINE_TYPE_PASTEURELLOSIS_CATTLE"

    if "anthrax" in v_low:
        if sp == "LIVESTOCK_SPECIES_GOAT":
            return "VACCINE_TYPE_ANTHRAX_GOAT"
        if sp == "LIVESTOCK_SPECIES_SHEEP":
            return "VACCINE_TYPE_ANTHRAX_SHEEP"
        if sp == "LIVESTOCK_SPECIES_CAMEL":
            return "VACCINE_TYPE_ANTHRAX_CAMEL"
        return "VACCINE_TYPE_ANTHRAX_CATTLE"

    if "blackleg" in v_low:
        return "VACCINE_TYPE_BLACKLEG"
    if "cbpp" in v_low:
        return "VACCINE_TYPE_CBPP"
    if "ccpp" in v_low:
        return "VACCINE_TYPE_CCPP"
    if "fmd" in v_low:
        return "VACCINE_TYPE_FMD_CATTLE"
    if "lsd" in v_low or "lumpy" in v_low:
        return "VACCINE_TYPE_LSD"
    if "brucellosis" in v_low:
        return "VACCINE_TYPE_BRUCELLOSIS_S19"
    if "rabies" in v_low:
        if sp == "LIVESTOCK_SPECIES_DONKEY":
            return "VACCINE_TYPE_RABIES_DONKEY"
        return "VACCINE_TYPE_RABIES_CATTLE"
    if "ppr" in v_low:
        if sp == "LIVESTOCK_SPECIES_SHEEP":
            return "VACCINE_TYPE_PPR_SHEEP"
        return "VACCINE_TYPE_PPR_GOAT"
    if "sgp" in v_low or "pox" in v_low:
        if sp == "LIVESTOCK_SPECIES_SHEEP":
            return "VACCINE_TYPE_SGP_SHEEP"
        if sp == "LIVESTOCK_SPECIES_CAMEL":
            return "VACCINE_TYPE_CAMEL_POX_VACCINE"
        if sp == "LIVESTOCK_SPECIES_POULTRY":
            return "VACCINE_TYPE_FOWL_POX"
        return "VACCINE_TYPE_SGP_GOAT"
    if "enterotoxaemia" in v_low:
        return "VACCINE_TYPE_ENTEROTOXAEMIA"
    if "newcastle" in v_low:
        return "VACCINE_TYPE_NEWCASTLE"
    if "gumboro" in v_low:
        return "VACCINE_TYPE_GUMBORO"
    if "fowl_typhoid" in v_low:
        return "VACCINE_TYPE_FOWL_TYPHOID"
    if "marek" in v_low:
        return "VACCINE_TYPE_MAREK"
    if "ahs" in v_low:
        if sp == "LIVESTOCK_SPECIES_DONKEY":
            return "VACCINE_TYPE_AHS_DONKEY"
        return "VACCINE_TYPE_AHS"
    if "tetanus" in v_low:
        return "VACCINE_TYPE_TETANUS_HORSE"
    if v_low in ("routine", ""):
        return "ROUTINE"
    return v.upper()


# Form `disease` choice (livestock_registry.xlsx, choices sheet) -> registry
# LIVESTOCK_DISEASE attribute value. Mirrors disease_map in
# templates/ls_odk_transform.j2; keep the two in step.
_DISEASE_CANONICAL_MAP = {
    "anthrax": "LIVESTOCK_DISEASE_ANTHRAX",
    "blackleg": "LIVESTOCK_DISEASE_BLACKLEG",
    "contagious_bovine_pleuropneumonia": "LIVESTOCK_DISEASE_CBPP",
    "cbpp": "LIVESTOCK_DISEASE_CBPP",
    "contagious_caprine_pleuropneumonia": "LIVESTOCK_DISEASE_CCPP",
    "ccpp": "LIVESTOCK_DISEASE_CCPP",
    "foot_and_mouth_disease": "LIVESTOCK_DISEASE_FMD",
    "fmd": "LIVESTOCK_DISEASE_FMD",
    "lumpy_skin_disease": "LIVESTOCK_DISEASE_LSD",
    "lsd": "LIVESTOCK_DISEASE_LSD",
    "peste_des_petits_ruminants": "LIVESTOCK_DISEASE_PPR",
    "ppr": "LIVESTOCK_DISEASE_PPR",
    "sheep_and_goat_pox": "LIVESTOCK_DISEASE_SHEEP_GOAT_POX",
    "newcastle_disease": "LIVESTOCK_DISEASE_NEWCASTLE_DISEASE",
    "gumboro": "LIVESTOCK_DISEASE_GUMBORO_DISEASE",
    "fowl_typhoid": "LIVESTOCK_DISEASE_FOWL_TYPHOID_DISEASE",
    "fowl_pox": "LIVESTOCK_DISEASE_FOWL_POX_DISEASE",
    "rabies": "LIVESTOCK_DISEASE_RABIES",
    "brucellosis": "LIVESTOCK_DISEASE_BRUCELLOSIS",
    "trypanosomiasis": "LIVESTOCK_DISEASE_TRYPANOSOMIASIS",
    "mastitis": "LIVESTOCK_DISEASE_MASTITIS",
    "internal_parasites": "LIVESTOCK_DISEASE_INTERNAL_PARASITES",
    "external_parasites": "LIVESTOCK_DISEASE_EXTERNAL_PARASITES",
    "pasteurellosis": "LIVESTOCK_DISEASE_PASTEURELLOSIS",
    "bovine_tuberculosis": "LIVESTOCK_DISEASE_BOVINE_TB",
    "camel_pox": "LIVESTOCK_DISEASE_CAMEL_POX",
    "african_horse_sickness": "LIVESTOCK_DISEASE_AFRICAN_HORSE_SICKNESS",
    "enterotoxaemia": "LIVESTOCK_DISEASE_ENTEROTOXAEMIA_DISEASE",
    "coccidiosis": "LIVESTOCK_DISEASE_COCCIDIOSIS",
    "foot_rot": "LIVESTOCK_DISEASE_FOOT_ROT",
    "bloat": "LIVESTOCK_DISEASE_BLOAT",
    "diarrhoea": "LIVESTOCK_DISEASE_DIARRHOEA",
    "retained_placenta": "LIVESTOCK_DISEASE_RETAINED_PLACENTA",
    "other": "LIVESTOCK_DISEASE_OTHER_DISEASE",
}


def normalize_disease(disease_val: str | None) -> str | None:
    """Normalize a raw disease string into the LIVESTOCK_DISEASE attribute value_id.

    Unlike normalize_species/normalize_vaccine there is no fallback guess: a
    value that is not a known form choice or an existing code is returned as
    is, so the health/vital-event validation rejects the row with the same
    message a staff entry would get, instead of relabelling it."""
    if not disease_val:
        return None
    d = str(disease_val).strip()
    if not d:
        return None
    if d.upper().startswith("LIVESTOCK_DISEASE_"):
        return d.upper()
    return _DISEASE_CANONICAL_MAP.get(d.lower(), d)


def _alias_extension_submodules():
    """Alias all openg2p_registry_livestock_extension submodules as openg2p_registry_extensions."""
    target = "openg2p_registry_livestock_extension"
    alias = "openg2p_registry_extensions"
    try:
        import openg2p_registry_livestock_extension
        sys.modules[alias] = openg2p_registry_livestock_extension
    except Exception:
        pass

    try:
        import openg2p_registry_livestock_extension.register_domain.services
        import openg2p_registry_livestock_extension.register_domain.models
        import openg2p_registry_livestock_extension.register_domain.factory
        import openg2p_registry_livestock_extension.config
    except Exception:
        pass

    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith(target):
            alias_name = alias + mod_name[len(target):]
            sys.modules[alias_name] = sys.modules[mod_name]
        elif mod_name.startswith(alias):
            target_name = target + mod_name[len(alias):]
            sys.modules[target_name] = sys.modules[mod_name]


def _ensure_domain_factory_initialized():
    """Ensure template helper, document service, and extension alias are initialized cleanly."""
    _alias_extension_submodules()
    try:
        from openg2p_registry_core.helpers.template_helper import TemplateHelper
        if TemplateHelper.get_component() is None:
            TemplateHelper()
    except Exception:
        pass

    try:
        from openg2p_registry_core.services import G2PDocumentService
        if G2PDocumentService.get_component() is None:
            G2PDocumentService()
    except Exception:
        pass

    try:
        from openg2p_registry_core.services.g2p_awe_integration_service import G2PAweIntegrationService
        if G2PAweIntegrationService.get_component() is None:
            G2PAweIntegrationService()
    except Exception:
        pass

    # ingest_data resolves the data model's response template through this
    # service; the celery worker's Initializer never creates it, so File Import
    # rows failed with "'NoneType' object has no attribute
    # 'resolve_template_store_id'" right after being saved.
    try:
        from openg2p_registry_core.services.g2p_template_service import G2PTemplateService
        if G2PTemplateService.get_component() is None:
            G2PTemplateService()
    except Exception:
        pass

    # Finalizing an ingested submission starts its AWE approval, which goes
    # through G2PAwePolicyConfigurationService (find_effective_policy_
    # configuration, cached with fastapi-cache), AweHelper and the services
    # the staff-api's Initializer creates but the celery worker's does not.
    # Without them every ODK ingest failed at finalize with "'NoneType' object
    # has no attribute 'find_effective_policy_configuration'" and no approval
    # request was ever created. Same set the farmer registry's worker patch
    # creates; each one is optional so a platform version without it still
    # imports (G2PAttributeValueValidator, for instance, is newer than 296).
    try:
        from fastapi_cache import FastAPICache
        from openg2p_registry_core.cache import init_cache
        try:
            FastAPICache.get_backend()
        except Exception:
            init_cache()
    except Exception:
        pass
    for _module, _name in (
        ("openg2p_registry_core.helpers.awe_helper", "AweHelper"),
        ("openg2p_registry_core.services.g2p_awe_policy_configuration_service", "G2PAwePolicyConfigurationService"),
        ("openg2p_registry_core.services.g2p_completion_score_service", "G2PCompletionScoreService"),
        ("openg2p_registry_core.services.g2p_register_history_service", "G2PRegisterHistoryService"),
        ("openg2p_registry_core.services.g2p_score_compute_service", "G2PScoreComputeService"),
        ("openg2p_registry_core.services.g2p_verification_service", "G2PRegisterVerificationService"),
        ("openg2p_registry_core.services.g2p_attribute_value_validator", "G2PAttributeValueValidator"),
    ):
        try:
            _cls = getattr(importlib.import_module(_module), _name)
            if _cls.get_component() is None:
                _cls()
        except Exception as _exc:
            _logger.debug("ODK Hook: optional worker component %s not created: %s", _name, _exc)



def _patch_celery_transformation_worker():
    """Patch Session.add and _transform_enriched_data_json for Celery transformation worker."""
    try:
        from sqlalchemy.orm import Session
        if not hasattr(Session, "_ls_orig_add"):
            orig_add = Session.add
            Session._ls_orig_add = orig_add

            def patched_add(self, instance, _warn=True):
                try:
                    from openg2p_registry_core.models.ingestion_pipeline import IncomingEnrichedTransformedData
                    if isinstance(instance, IncomingEnrichedTransformedData) and instance.ingest_id:
                        existing = self.get(IncomingEnrichedTransformedData, instance.ingest_id)
                        if existing and existing is not instance:
                            existing.enriched_data_json = instance.enriched_data_json
                            existing.transformed_data_json = instance.transformed_data_json
                            existing.enriched_data_xml = instance.enriched_data_xml
                            existing.transformed_data_xml = instance.transformed_data_xml
                            return existing
                except Exception:
                    pass
                return orig_add(self, instance, _warn=_warn)

            Session.add = patched_add
            _logger.info("ODK Hook: Successfully patched Session.add for Celery transformation worker")
    except Exception as e:
        _logger.debug("ODK Hook: Could not patch Session.add: %s", e)

    try:
        import importlib
        importlib.import_module("openg2p_registry_celery_worker.tasks.ingest_data_transformation_worker")
        tw = sys.modules.get("openg2p_registry_celery_worker.tasks.ingest_data_transformation_worker")
        if tw and not hasattr(tw, "_ls_orig_transform_json"):
            orig_transform_json = tw._transform_enriched_data_json
            tw._ls_orig_transform_json = orig_transform_json

            def patched_transform_json(incoming_classified_data, enriched_data_json, session):
                tmpl = _load_transform_template()
                if tmpl:
                    try:
                        payload = enriched_data_json
                        if isinstance(payload, dict):
                            if "body" in payload and isinstance(payload["body"], dict):
                                payload = payload["body"].get("message", {}).get("payload", payload)
                            elif "message" in payload and isinstance(payload["message"], dict):
                                payload = payload["message"].get("payload", payload)

                        rendered = tmpl.render(expanded=payload)
                        transformed = json.loads(rendered)
                        _logger.info("ODK Hook: Successfully transformed enriched data using local ls_odk_transform.j2")
                        return transformed
                    except Exception as err_tmpl:
                        _logger.error("ODK Hook: Error rendering local transformation template: %s", err_tmpl)
                return orig_transform_json(incoming_classified_data, enriched_data_json, session)

            tw._transform_enriched_data_json = patched_transform_json
            _logger.info("ODK Hook: Successfully patched _transform_enriched_data_json")
    except Exception as e:
        _logger.debug("ODK Hook: Could not patch _transform_enriched_data_json: %s", e)


def _patch_celery_ingest_worker():
    """Patch ingest_data_worker to auto-approve and promote intake form records to live registers."""
    try:
        import importlib
        # Ensure openg2p_registry_extensions alias is active before loading worker
        import openg2p_registry_livestock_extension
        sys.modules["openg2p_registry_extensions"] = openg2p_registry_livestock_extension
        import openg2p_registry_livestock_extension.config
        sys.modules["openg2p_registry_extensions.config"] = openg2p_registry_livestock_extension.config

        # Patch G2PIntakeFormDataService._insert_live_register_row to sanitize enums and enrich livestock/child records
        try:
            from openg2p_registry_core.services.intake_form_data_service import G2PIntakeFormDataService
            if not hasattr(G2PIntakeFormDataService, "_ls_orig_insert_live"):
                _orig_ilrr = G2PIntakeFormDataService._insert_live_register_row
                G2PIntakeFormDataService._ls_orig_insert_live = _orig_ilrr

                async def _safe_insert_live_register_row(
                    self,
                    submission,
                    section,
                    register_definition,
                    schema_class,
                    register_class,
                    intake_row,
                    session,
                ):
                    # Sanitize attributes on intake_row to conform to livestock register schema enums.
                    # Only an Animal row has the DRAFT/CONFIRMED/DONE state: the Livestock
                    # holding's `state` is the Kebele -> Region approval ladder
                    # (LivestockStateEnum) and must not be rewritten here, or every ODK
                    # record would skip the ladder it is meant to go through.
                    if (
                        getattr(register_class, "__tablename__", "") == "g2p_register_animals"
                        and hasattr(intake_row, "state")
                        and getattr(intake_row, "state", None) not in ("DRAFT", "CONFIRMED", "DONE")
                    ):
                        intake_row.state = "CONFIRMED"
                    if hasattr(intake_row, "event_type"):
                        et = str(getattr(intake_row, "event_type", "") or "").upper()
                        if "AI" in et or "INSEMINATION" in et:
                            intake_row.event_type = "AI"
                        elif "NATURAL" in et:
                            intake_row.event_type = "NATURAL"
                    if hasattr(intake_row, "location"):
                        loc = str(getattr(intake_row, "location", "") or "").upper()
                        if "HOME" in loc:
                            intake_row.location = "HOME"
                        elif "VET" in loc:
                            intake_row.location = "VETERINARY"
                        elif "MARKET" in loc:
                            intake_row.location = "MARKET"
                        elif "FIELD" in loc:
                            intake_row.location = "FIELD"
                        elif "QUARANTINE" in loc:
                            intake_row.location = "QUARANTINE_CENTER"
                        elif loc and loc not in ("HOME", "VETERINARY", "MARKET", "FIELD", "QUARANTINE_CENTER", "OTHER"):
                            intake_row.location = "OTHER"

                    # If this is Livestock or Farmer register, ensure geo labels are populated
                    is_livestock = getattr(register_class, "__tablename__", "") == "g2p_register_livestocks"
                    is_farmer = getattr(register_class, "__tablename__", "") == "g2p_register_farmers"
                    if is_livestock or is_farmer:
                        try:
                            # 1. Resolve Geo Labels
                            for geo_field in ("region", "zone", "woreda", "kebele"):
                                cur_val = getattr(intake_row, geo_field, None)
                                if cur_val:
                                    lbl = await resolve_geo_label(cur_val, geo_field)
                                    if lbl:
                                        setattr(intake_row, geo_field, lbl)
                        except Exception as ex_geo_res:
                            _logger.warning("ODK Hook: Error resolving geo labels for %s: %s", getattr(register_class, "__tablename__", ""), ex_geo_res)

                    if is_livestock:
                        try:

                            # 2. Synchronize Farmer details
                            from sqlalchemy import select, func
                            from openg2p_registry_extensions.register_domain.models import (
                                G2PIntakeFormFarmer, G2PRegisterFarmer, G2PIntakeFormAnimal
                            )
                            f_row = (await session.execute(
                                select(G2PIntakeFormFarmer).where(G2PIntakeFormFarmer.submission_id == submission.submission_id)
                            )).scalar_one_or_none()
                            if not f_row and hasattr(submission, "application_reference") and submission.application_reference:
                                f_row = (await session.execute(
                                    select(G2PIntakeFormFarmer).where(G2PIntakeFormFarmer.application_reference == submission.application_reference)
                                )).scalar_one_or_none()

                            farmer_name = None
                            farmer_id = None
                            fayda_fan_id = None
                            if f_row:
                                farmer_name = f_row.farmer_name or _full_name(f_row.first_name, f_row.middle_name, f_row.last_name)
                                farmer_id = f_row.farmer_id
                                fayda_fan_id = f_row.fayda_fan_id

                            if farmer_name:
                                intake_row.farmer_name = farmer_name
                                intake_row.record_name = farmer_name
                            elif getattr(intake_row, "farmer_name", None):
                                intake_row.record_name = intake_row.farmer_name

                            if farmer_id:
                                intake_row.farmer_id = farmer_id
                            if fayda_fan_id:
                                intake_row.fayda_fan_id = fayda_fan_id

                            # 3. Total Animals
                            if not getattr(intake_row, "total_animals", None):
                                anim_count = (await session.execute(
                                    select(func.count()).select_from(G2PIntakeFormAnimal).where(
                                        G2PIntakeFormAnimal.submission_id == submission.submission_id
                                    )
                                )).scalar() or 0
                                intake_row.total_animals = anim_count
                        except Exception as ex_ls_sync:
                            _logger.warning("ODK Hook: Error prepping intake_row for livestock live insert: %s", ex_ls_sync)

                    # Ensure child records link to livestock internal_record_id
                    is_child_table = getattr(register_class, "__tablename__", "") in (
                        "g2p_register_animals", "g2p_register_health_events",
                        "g2p_register_vaccinations", "g2p_register_vital_events",
                        "g2p_register_breedings"
                    )
                    if is_child_table and not getattr(intake_row, "link_internal_record_id", None):
                        try:
                            from sqlalchemy import select
                            from openg2p_registry_extensions.register_domain.models import G2PIntakeFormLivestock, G2PRegisterLivestock
                            ls_parent_id = (await session.execute(
                                select(G2PIntakeFormLivestock.internal_record_id).where(
                                    G2PIntakeFormLivestock.submission_id == submission.submission_id
                                )
                            )).scalar()
                            if not ls_parent_id and hasattr(submission, "application_reference") and submission.application_reference:
                                ls_parent_id = (await session.execute(
                                    select(G2PRegisterLivestock.internal_record_id).where(
                                        G2PRegisterLivestock.link_internal_record_id == submission.application_reference
                                    )
                                )).scalar()
                            if ls_parent_id:
                                intake_row.link_internal_record_id = ls_parent_id
                        except Exception as ex_link:
                            _logger.debug("ODK Hook: Link internal_record_id lookup error: %s", ex_link)

                    # Normalize species, breed, and vaccine_type on intake_row if present
                    if hasattr(intake_row, "species") and getattr(intake_row, "species", None):
                        intake_row.species = normalize_species(intake_row.species)
                    if hasattr(intake_row, "breed") and getattr(intake_row, "breed", None):
                        intake_row.breed = normalize_breed(intake_row.breed, getattr(intake_row, "species", None))
                    if hasattr(intake_row, "vaccine_type") and getattr(intake_row, "vaccine_type", None):
                        intake_row.vaccine_type = normalize_vaccine(intake_row.vaccine_type, getattr(intake_row, "species", None))

                    # Call original live register row insert
                    live_row = await _orig_ilrr(
                        self,
                        submission,
                        section,
                        register_definition,
                        schema_class,
                        register_class,
                        intake_row,
                        session,
                    )

                    # Post-insert propagation for livestock and farmer
                    if live_row:
                        try:
                            if is_livestock:
                                for attr in ("record_name", "farmer_name", "farmer_id", "fayda_fan_id", "total_animals", "region", "zone", "woreda", "kebele"):
                                    ival = getattr(intake_row, attr, None)
                                    if ival is not None:
                                        setattr(live_row, attr, ival)
                                if not live_row.record_name and live_row.farmer_name:
                                    live_row.record_name = live_row.farmer_name
                                from openg2p_registry_extensions.register_domain.services import G2PRegisterDomainServiceLivestock
                                live_row.search_text = G2PRegisterDomainServiceLivestock().construct_search_text(live_row.to_dict())
                            elif is_farmer:
                                for attr in ("region", "zone", "woreda", "kebele"):
                                    ival = getattr(intake_row, attr, None)
                                    if ival is not None:
                                        setattr(live_row, attr, ival)
                                from openg2p_registry_extensions.register_domain.services import G2PRegisterDomainServiceFarmer
                                live_row.search_text = G2PRegisterDomainServiceFarmer().construct_search_text(live_row.to_dict())

                            for attr in ("species", "breed", "vaccine_type"):
                                ival = getattr(intake_row, attr, None)
                                if ival is not None and hasattr(live_row, attr):
                                    setattr(live_row, attr, ival)
                        except Exception as ex_post:
                            _logger.warning("ODK Hook: Error updating live_row: %s", ex_post)

                    # Post-insert offspring generation for BIRTH events
                    if getattr(register_class, "__tablename__", "") == "g2p_register_vital_events" and live_row:
                        try:
                            if str(getattr(live_row, "event_type", "") or "").upper() == "BIRTH":
                                from openg2p_registry_extensions.register_domain.services.g2p_register_domain_service_vital_event import (
                                    G2PRegisterDomainServiceVitalEvent
                                )
                                await G2PRegisterDomainServiceVitalEvent()._maybe_generate_offspring(live_row, session)
                        except Exception as ex_birth:
                            _logger.warning("ODK Hook: Error generating offspring for birth event: %s", ex_birth)

                    return live_row

                G2PIntakeFormDataService._insert_live_register_row = _safe_insert_live_register_row
                _logger.info("ODK Hook: Successfully wrapped G2PIntakeFormDataService._insert_live_register_row")
        except Exception as err_ilrr:
            _logger.warning("ODK Hook: Could not wrap _insert_live_register_row: %s", err_ilrr)

        importlib.import_module("openg2p_registry_celery_worker.tasks.ingest_data_worker")
        worker_mod = sys.modules.get("openg2p_registry_celery_worker.tasks.ingest_data_worker")

        if worker_mod and hasattr(worker_mod, "_validate_transformed_data_json") and not hasattr(worker_mod, "_ls_orig_vtdj"):
            orig_vtdj = worker_mod._validate_transformed_data_json
            worker_mod._ls_orig_vtdj = orig_vtdj

            def safe_validate_transformed_data_json(
                incoming_classified_data,
                incoming_enriched_transformed_data,
                ordered_sections,
            ):
                tdj = incoming_enriched_transformed_data.transformed_data_json
                if isinstance(tdj, dict):
                    allowed = {s.section_mnemonic for s in ordered_sections}
                    filtered = {k: v for k, v in tdj.items() if k in allowed}
                    incoming_enriched_transformed_data.transformed_data_json = filtered
                return orig_vtdj(
                    incoming_classified_data,
                    incoming_enriched_transformed_data,
                    ordered_sections,
                )

            worker_mod._validate_transformed_data_json = safe_validate_transformed_data_json

        if worker_mod and hasattr(worker_mod, "_save_sections_async") and not hasattr(worker_mod, "_ls_orig_save_sections_async"):
            orig_save_sections_async = worker_mod._save_sections_async
            worker_mod._ls_orig_save_sections_async = orig_save_sections_async

            async def patched_save_sections_async(
                submission_id: str,
                incoming_classified_data,
                ordered_sections: list,
                transformed_data: dict,
                session,
            ) -> None:
                # session.bind is this worker module's own pooled engine, tied to
                # its event loop. It is swapped in only for this save and restored
                # in the finally below: left in place, the next File Import task
                # in the same process drove it from another loop, failing with
                # "another operation is in progress" and leaving transactions
                # open that held row locks and stalled the whole pipeline.
                prev_dbengine = None
                swapped_dbengine = False
                try:
                    from openg2p_fastapi_common.context import dbengine
                    if hasattr(session, "bind") and session.bind:
                        prev_dbengine = dbengine.get()
                        dbengine.set(session.bind)
                        swapped_dbengine = True
                    else:
                        _ensure_dbengine_initialized()
                    _ensure_domain_factory_initialized()
                except Exception as ex_init:
                    _logger.warning("ODK Hook: Error during save initialization: %s", ex_init)

                # Pre-process transformed_data before saving
                f_name = None
                f_id = None
                f_fan = None
                animal_count = 0
                try:
                    # 1. Geo resolution on all location sections
                    for sec in ("ls_farmer_identity", "ls_farmer_location", "ls_livestock_location", "ls_livestock_record"):
                        rows = transformed_data.get(sec) or []
                        if isinstance(rows, list):
                            for r in rows:
                                if isinstance(r, dict):
                                    for g_fld in ("region", "zone", "woreda", "kebele"):
                                        if r.get(g_fld):
                                            r[g_fld] = await resolve_geo_label(r[g_fld], g_fld)

                    # 2. Synchronize farmer details & animal count to livestock sections
                    f_id_rows = transformed_data.get("ls_farmer_identity") or []
                    if f_id_rows and isinstance(f_id_rows[0], dict):
                        f0 = f_id_rows[0]
                        f_name = f0.get("farmer_name") or _full_name(f0.get("first_name"), f0.get("middle_name"), f0.get("last_name"))
                        f_id = f0.get("farmer_id")
                        f_fan = f0.get("fayda_fan_id")

                    animals = transformed_data.get("ls_animal_details") or []
                    animal_count = len(animals) if isinstance(animals, list) else 0

                    for ls_sec in ("ls_livestock_record", "ls_livestock_location"):
                        ls_rows = transformed_data.get(ls_sec) or []
                        if isinstance(ls_rows, list):
                            for r in ls_rows:
                                if isinstance(r, dict):
                                    if f_name:
                                        r["farmer_name"] = f_name
                                        r["record_name"] = f_name
                                    if f_id:
                                        r["farmer_id"] = f_id
                                    if f_fan:
                                        r["fayda_fan_id"] = f_fan
                                    r["total_animals"] = animal_count

                    # 3. Normalize species & breed for animals and build animal map
                    animal_map = {}
                    if isinstance(animals, list):
                        for a in animals:
                            if isinstance(a, dict):
                                sp = normalize_species(a.get("species") or a.get("species_id"))
                                a["species"] = sp
                                if a.get("breed"):
                                    a["breed"] = normalize_breed(a.get("breed"), sp)
                                if a.get("ear_tag_id"):
                                    animal_map[str(a["ear_tag_id"]).strip()] = a

                    for ev_sec in ("ls_health_event_details", "ls_vaccination_details", "ls_vital_event_details", "ls_breeding_details"):
                        ev_rows = transformed_data.get(ev_sec) or []
                        if isinstance(ev_rows, list):
                            for ev in ev_rows:
                                if isinstance(ev, dict):
                                    tag = str(ev.get("ear_tag_id") or "").strip()
                                    sp = None
                                    if tag in animal_map:
                                        a = animal_map[tag]
                                        if not ev.get("species"):
                                            ev["species"] = a.get("species")
                                        if not ev.get("age"):
                                            dob = a.get("date_of_birth")
                                            if dob:
                                                ev["age"] = _calc_age_str(dob)
                                            elif a.get("age"):
                                                ev["age"] = str(a.get("age"))
                                    if ev.get("species"):
                                        ev["species"] = normalize_species(ev["species"])
                                        sp = ev["species"]
                                    if ev_sec == "ls_vaccination_details" and ev.get("vaccine_type"):
                                        ev["vaccine_type"] = normalize_vaccine(ev["vaccine_type"], sp)
                                    if ev_sec in ("ls_health_event_details", "ls_vital_event_details") and ev.get("disease_type"):
                                        ev["disease_type"] = normalize_disease(ev["disease_type"])
                except Exception as ex_enrich:
                    _logger.warning("ODK Hook: Error enriching transformed_data: %s", ex_enrich)

                from .register_domain.services.domain_validation_utils import ingest_session

                t_session = ingest_session.set(session)
                try:
                    res = await orig_save_sections_async(
                        submission_id,
                        incoming_classified_data,
                        ordered_sections,
                        transformed_data,
                        session,
                    )

                    # Post-save safety check on G2PIntakeFormLivestock and G2PIntakeFormFarmer (Option B: Left in PENDING state)
                    try:
                        from sqlalchemy import select
                        from openg2p_registry_extensions.register_domain.models import G2PIntakeFormLivestock, G2PIntakeFormFarmer
                        from .register_domain.services.admin_area_sync import sync_admin_area
                        ls_intake_rows = (await session.execute(
                            select(G2PIntakeFormLivestock).where(G2PIntakeFormLivestock.submission_id == submission_id)
                        )).scalars().all()
                        for ls_row in ls_intake_rows:
                            if f_name:
                                ls_row.farmer_name = f_name
                                ls_row.record_name = f_name
                            if f_id:
                                ls_row.farmer_id = f_id
                            if f_fan:
                                ls_row.fayda_fan_id = f_fan
                            ls_row.total_animals = animal_count
                            for geo_field in ("region", "zone", "woreda", "kebele"):
                                cur_val = getattr(ls_row, geo_field, None)
                                if cur_val:
                                    lbl = await resolve_geo_label(cur_val, geo_field)
                                    if lbl:
                                        setattr(ls_row, geo_field, lbl)
                            await sync_admin_area(ls_row)
                            ls_row.status = "FINAL"

                        farmer_intake_rows = (await session.execute(
                            select(G2PIntakeFormFarmer).where(G2PIntakeFormFarmer.submission_id == submission_id)
                        )).scalars().all()
                        for f_row in farmer_intake_rows:
                            for geo_field in ("region", "zone", "woreda", "kebele"):
                                cur_val = getattr(f_row, geo_field, None)
                                if cur_val:
                                    lbl = await resolve_geo_label(cur_val, geo_field)
                                    if lbl:
                                        setattr(f_row, geo_field, lbl)
                            await sync_admin_area(f_row)
                            f_row.status = "FINAL"

                        await session.flush()
                        _logger.info("ODK Hook: Saved intake records for submission %s in PENDING state (Option B)", submission_id)
                    except Exception as ex_post_save:
                        _logger.warning("ODK Hook: Post-save intake update check: %s", ex_post_save)

                    return res
                finally:
                    ingest_session.reset(t_session)
                    if swapped_dbengine and prev_dbengine is not None:
                        try:
                            from openg2p_fastapi_common.context import dbengine
                            dbengine.set(prev_dbengine)
                        except Exception:
                            pass

            worker_mod._save_sections_async = patched_save_sections_async
            _logger.info("ODK Hook: Successfully patched ingest_data_worker._save_sections_async (Option B)")



    except Exception as e:
        _logger.warning("ODK Hook: Could not patch ingest_data_worker: %s", e)


def _ensure_dbengine_initialized():
    """Create the components the celery worker's Initializer does not, and
    install the transformation patches. The registry database engine itself
    is wired once, for every process, in the package __init__."""
    _ensure_domain_factory_initialized()
    _patch_celery_transformation_worker()



def _load_transform_template():
    """Load the Jinja2 transformation template for livestock ODK submissions."""
    dir_path = os.path.dirname(os.path.abspath(__file__))
    tmpl_path = os.path.join(dir_path, "templates", "ls_odk_transform.j2")
    if os.path.exists(tmpl_path):
        with open(tmpl_path, "r", encoding="utf-8") as f:
            return Template(f.read())
    return None


# File Import columns that describe the row's animal (the keys ls_odk_transform.j2
# reads from each entry of the `livestock` list).
_FILE_IMPORT_ANIMAL_COLUMNS = (
    "ear_tag_id", "secondary_identifier", "species", "breed", "colour", "weight",
    "quantity", "gender", "date_of_birth", "age", "health_status",
    "vaccination_status", "registration_date",
)


def _is_blank_cell(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _patch_ingest_service():
    """Patch G2PIngestService to transform and process ODK submissions smoothly."""
    try:
        from openg2p_registry_core.services.g2p_ingest_service import G2PIngestService
        if hasattr(G2PIngestService, "_ls_orig_ingest_data"):
            return

        orig_ingest_data = G2PIngestService.ingest_data
        G2PIngestService._ls_orig_ingest_data = orig_ingest_data

        async def patched_ingest_data(self, data_model_mnemonic: str, data: dict, *, register_id=None, intake_form_id=None):
            _ensure_dbengine_initialized()

            # Seeded by meta_data/data-models/data_models.sql (+ key paths and
            # semantic pattern); patch_livestock_odk_ingestion.sql for older DBs.
            target_data_model = "LIVESTOCK_ODK_MODEL"
            livestock_register_id = "997676d3-7008-59f9-b23e-613ad79bbb08"
            livestock_intake_form_id = "e92e8be1-207f-518e-99c2-8bc21cc1f112"

            # File Import (celery import_file_process_worker) sends each row as
            # {"headers": {...}, "body": <row>} with the import's own data model,
            # register and intake form. It is not an ODK submission: rewriting it
            # onto the ODK data model failed every row with DATA_MODEL_NOT_FOUND.
            is_file_import = (
                isinstance(data, dict)
                and isinstance(data.get("headers"), dict)
                and "body" in data
                and bool(data_model_mnemonic and register_id and intake_form_id)
            )
            if is_file_import:
                # The worker's {"headers", "body"} shape does not match the data
                # model's key paths ($.body.header.sender_id, $.body.signature,
                # $.body['header','message']), so re-wrap it. The row goes where
                # the model's semantic pattern reads the business payload
                # ($.body.message.search_response[0].data.reg_records[0]); the
                # transformation step renders it with ls_odk_transform.j2, whose
                # flat keys (farmer_id, fayda_fan_id, owner_id, region, ...) are
                # the import file's columns.
                headers = data["headers"]
                row = data["body"]
                # A CSV / Excel row is flat, but the template reads animals from a
                # `livestock` list. Animal columns on the row (ear_tag_id,
                # species, breed, ...) become that row's one animal.
                if isinstance(row, dict) and not row.get("livestock"):
                    animal = {
                        k: row[k] for k in _FILE_IMPORT_ANIMAL_COLUMNS
                        if not _is_blank_cell(row.get(k))
                    }
                    if animal.get("ear_tag_id") or animal.get("species"):
                        row = dict(row, livestock=[animal])
                data = {
                    "body": {
                        "header": {
                            "sender_id": headers.get("sender_id") or "Staff Portal",
                            "message_id": headers.get("message_id") or uuid.uuid4().hex,
                        },
                        "signature": headers.get("signature") or "file-import",
                        "message": {
                            "search_response": [{"data": {"reg_records": [row]}}],
                        },
                    }
                }

            if isinstance(data, dict) and not is_file_import:
                has_envelope = (
                    ("header" in data and "message" in data) or
                    (isinstance(data.get("body"), dict) and "message" in data.get("body", {}))
                )
                if not has_envelope:
                    instance_id = (
                        data.get("instanceID")
                        or (data.get("meta") or {}).get("instanceID")
                        or (data.get("__system") or {}).get("submissionId")
                        or str(uuid.uuid4())
                    )
                    if isinstance(instance_id, str) and instance_id.startswith("uuid:"):
                        instance_id = instance_id[5:]

                    data = {
                        "body": {
                            "header": {
                                "sender_id": "Livestock",
                                "message_id": instance_id,
                                "signature": "dummy_sig"
                            },
                            "message": {
                                "payload": data
                            }
                        }
                    }

                data_model_mnemonic = target_data_model
                if not register_id:
                    register_id = livestock_register_id
                if not intake_form_id:
                    intake_form_id = livestock_intake_form_id

            data = _make_json_serializable(data)

            res = await orig_ingest_data(
                self,
                data_model_mnemonic,
                data,
                register_id=register_id,
                intake_form_id=intake_form_id,
            )
            return _make_json_serializable(res)

        G2PIngestService.ingest_data = patched_ingest_data
        _logger.info("ODK Hook: Successfully patched G2PIngestService")
    except Exception as e:
        _logger.error("ODK Hook: Error patching G2PIngestService: %s", e)


def install_odk_hooks():
    funcs = [
        _ensure_domain_factory_initialized,
        _patch_celery_transformation_worker,
        _patch_celery_ingest_worker,
        _ensure_dbengine_initialized,
        _patch_ingest_service,
    ]
    for func in funcs:
        print(f"ODK Hook: Running {func.__name__}", flush=True)
        try:
            func()
        except Exception as e:
            _logger.error("ODK Hook: Error in %s: %s", func.__name__, e, exc_info=True)


# Initialize hooks on import
install_odk_hooks()
