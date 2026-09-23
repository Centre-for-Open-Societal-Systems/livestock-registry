-- Pre-configure the Livestock Registry ODK Central pipeline in the connector database.
\connect connector

CREATE TABLE IF NOT EXISTS connector_definitions (
    connector_id character varying NOT NULL PRIMARY KEY,
    name character varying(255) NOT NULL UNIQUE,
    platform character varying(64) NOT NULL,
    transport_type character varying(64) NOT NULL,
    enabled boolean DEFAULT true,
    paused boolean DEFAULT false,
    data_model_mnemonic character varying(128),
    mapper_expression text,
    mapper_version character varying(64),
    g2p_sender_id character varying(128),
    g2p_register_mnemonic character varying(128),
    source_config_json text,
    auth_type character varying(64) DEFAULT 'none' NOT NULL,
    auth_secret_json text,
    webhook_secret character varying(512),
    webhook_path_slug character varying(128),
    webhook_verifier character varying(64) DEFAULT 'hmac_sha256' NOT NULL,
    last_poll_at timestamp without time zone,
    last_poll_status character varying(32),
    last_poll_error text,
    last_poll_fetched integer,
    last_poll_duration_ms integer,
    max_in_flight integer,
    validation_schema_json text,
    poll_config_json text,
    poll_state_json text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

INSERT INTO connector_definitions (
    connector_id, name, platform, transport_type, enabled, paused, data_model_mnemonic,
    g2p_sender_id, g2p_register_mnemonic,
    source_config_json, auth_type, auth_secret_json, webhook_verifier
) VALUES
(
    '11a22b33c44d55e66f77a88b99c00d11',
    'Livestock Registry - ODK Ingestion',
    'odk_central',
    'odk_central',
    true,
    false,
    'LS_DATA_MODEL',
    'Livestock',
    'Livestock',
    '{"base_url": "https://odk.13.207.43.8.nip.io", "project_id": 14, "form_id": "livestock_registry", "resolve_nav_links": true, "strict_incremental": false, "target_url": "http://partner-api:8000/partner/ingest_data", "target_headers": {"partner-id": "livestock-partner", "Content-Type": "application/json"}}',
    'odk_session',
    '{"email": "vilbertraj21@gmail.com", "password": "odksandbox"}',
    'hmac_sha256'
)
ON CONFLICT (connector_id) DO UPDATE SET
    name = EXCLUDED.name,
    platform = EXCLUDED.platform,
    transport_type = EXCLUDED.transport_type,
    enabled = EXCLUDED.enabled,
    paused = EXCLUDED.paused,
    data_model_mnemonic = EXCLUDED.data_model_mnemonic,
    g2p_sender_id = EXCLUDED.g2p_sender_id,
    g2p_register_mnemonic = EXCLUDED.g2p_register_mnemonic,
    source_config_json = EXCLUDED.source_config_json,
    auth_type = EXCLUDED.auth_type,
    auth_secret_json = EXCLUDED.auth_secret_json,
    webhook_verifier = EXCLUDED.webhook_verifier;
