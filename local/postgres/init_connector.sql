-- Connector Service database bootstrap (separate file)
CREATE ROLE connector_user WITH LOGIN PASSWORD 'connector_pass';
CREATE DATABASE connector OWNER connector_user;
\connect connector
GRANT ALL ON SCHEMA public TO connector_user;
