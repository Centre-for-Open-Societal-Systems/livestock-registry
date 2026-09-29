{{/*
Shared pieces of the reporting layer: the lr_rpt_* views (reporting-views.yaml),
their refresh CronJob (reporting-views-refresh.yaml) and the dashboard service
that reads them (dashboard-api.yaml).

This chart has no other templates; everything else comes from the
openg2p-registry subchart, whose own values (global.*, registry.*) a parent
template cannot see. So the database coordinates are declared under
`reporting.db` / `reporting.masterData`, defaulting to the subchart's naming
convention: database and user from the release name, password in the Secret
named after the release.
*/}}

{{/* Registry database host: reporting.db.host, else global.postgresqlHost. */}}
{{- define "livestock.reporting.dbHost" -}}
{{- tpl (.Values.reporting.db.host | default .Values.global.postgresqlHost | default "commons-postgresql") . -}}
{{- end }}

{{/* Image the reporting jobs run in: the registry's own db-seed image, which
     carries reporting_views.sql and reporting-geo-sync.sh. CI rewrites its tag. */}}
{{- define "livestock.reporting.image" -}}
{{- $repo := .Values.reporting.image.repository | default .Values.registry.dbSeed.image.repository -}}
{{- $tag := .Values.reporting.image.tag | default .Values.registry.dbSeed.image.tag -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end }}

{{/* libpq variables for the registry database. */}}
{{- define "livestock.reporting.dbEnv" -}}
- name: PGHOST
  value: {{ include "livestock.reporting.dbHost" . | quote }}
- name: PGPORT
  value: {{ .Values.reporting.db.port | toString | quote }}
- name: PGDATABASE
  value: {{ tpl .Values.reporting.db.name . | quote }}
- name: PGUSER
  value: {{ tpl .Values.reporting.db.user . | quote }}
- name: PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ tpl .Values.reporting.db.secret . | quote }}
      key: {{ tpl .Values.reporting.db.passwordKey . | quote }}
{{- end }}

{{/* Master Data connection for reporting-geo-sync.sh. Master Data is a separate
     database owned by a separate role; the registry user cannot read it. */}}
{{- define "livestock.reporting.mdsEnv" -}}
{{- with .Values.reporting.masterData }}
- name: MDS_DB
  value: {{ tpl .name $ | quote }}
- name: MDS_PGHOST
  value: {{ tpl (.host | default (include "livestock.reporting.dbHost" $)) $ | quote }}
- name: MDS_PGPORT
  value: {{ .port | toString | quote }}
- name: MDS_PGUSER
  value: {{ tpl .user $ | quote }}
- name: MDS_PGPASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ tpl .secret $ | quote }}
      key: {{ tpl .passwordKey $ | quote }}
{{- end }}
{{- end }}
