"""FARMER_CHANGED_V1 is seeded next to FARMER_REFERENCE_CHANGED_V1 and accepts both event types."""
import importlib
import json
import os
import re
from pathlib import Path
import sys
import unittest

PACKAGE=os.environ.get('REGISTRY_EXTENSION_MODULE','openg2p_registry_livestock_extension')
sys.modules.setdefault('openg2p_registry_extensions',importlib.import_module(PACKAGE))
notification=importlib.import_module(PACKAGE+'.farmer_reference.notification')
enrichers=importlib.import_module(PACKAGE+'.ingestion_pipeline.enricher_services')
from jinja2 import Environment

ROOT=Path(importlib.import_module(PACKAGE).__file__).parent
SEED=(ROOT/'meta_data/registry-inbound-message-rules/zz_farmer_changed_v1.sql').read_text(encoding='utf-8')
EVENT={'event_id':'synthetic-event','farmer_id':'FR-000000000001','fayda_fan_id':'0000000000000001'}


class FarmerChangedTests(unittest.TestCase):
    def test_both_event_types_are_accepted_and_others_are_not(self):
        for event_type in ('farmer-registry.farmer.changed.v1','farmer_reference.changed.v1'):
            with self.subTest(event_type=event_type):
                self.assertEqual(notification.notification_identity({**EVENT,'event_type':event_type}),
                                 ('FR-000000000001','0000000000000001'))
        for event_type in ('farmer-registry.farmer.changed.v2','farmer.changed.v1',None):
            with self.subTest(event_type=event_type),self.assertRaises(ValueError):
                notification.notification_identity({**EVENT,'event_type':event_type})

    def test_seed_patterns_match_both_event_types(self):
        patterns=set(re.findall(r"\$\.body\.message\.payload\.event_type=>(\^\(farmer[^']+)'",SEED))
        self.assertTrue(patterns)
        for pattern in patterns:
            for event_type in ('farmer-registry.farmer.changed.v1','farmer_reference.changed.v1'):
                with self.subTest(pattern=pattern,event_type=event_type):
                    self.assertTrue(re.match(pattern,event_type))
            self.assertFalse(re.match(pattern,'farmer-registry.farmer.changed.v10'))

    def test_seed_names_the_enricher_and_templates_that_exist(self):
        for enricher in set(re.findall(r"'([A-Za-z]+Enricher)'",SEED)):
            with self.subTest(enricher=enricher): self.assertTrue(hasattr(enrichers,enricher))
        self.assertIs(enrichers.G2PFarmerReferenceNotificationEnricher,enrichers.FarmerChangedEnricher)
        for name in set(re.findall(r"'([a-z0-9_]+\.j2)'",SEED)):
            with self.subTest(template=name):
                self.assertTrue(name.startswith('livestock_'))
                self.assertTrue((ROOT/'templates'/name).is_file())
        self.assertIn("'FARMER_CHANGED_V1'",SEED)
        self.assertNotIn('873c2342',SEED)

    def test_update_template_renders_only_the_identity(self):
        enriched=enrichers.FarmerChangedEnricher().enrich({**EVENT,'event_type':'farmer-registry.farmer.changed.v1'},None)
        template=(ROOT/'templates/livestock_farmer_changed_v1_update.j2').read_text(encoding='utf-8')
        rendered=json.loads(Environment().from_string(template).render(expanded={**enriched,'first_name':'Untrusted'}))
        self.assertEqual(next(iter(rendered.values())),[enriched])


if __name__=='__main__':unittest.main()
