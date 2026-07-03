{{- define "postgresql.fullname" -}}
{{- printf "%s-postgresql" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "postgresql.labels" -}}
app.kubernetes.io/name: postgresql
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: postgresql
{{- end -}}

{{- define "postgresql.selectorLabels" -}}
app.kubernetes.io/name: postgresql
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: postgresql
{{- end -}}

{{- define "postgresql.validate" -}}
{{- if .Values.enabled -}}
  {{- $adminPassword := required "postgresql.auth.postgresPassword is required; provide it through the SOPS values file" .Values.auth.postgresPassword -}}
  {{- $password := required "postgresql.auth.password is required; provide it through the SOPS values file" .Values.auth.password -}}
  {{- $username := required "postgresql.auth.username is required" .Values.auth.username -}}
  {{- $database := required "postgresql.auth.database is required" .Values.auth.database -}}
  {{- if or (gt (len $username) 63) (not (regexMatch "^[A-Za-z_][A-Za-z0-9_]*$" $username)) -}}
    {{- fail "postgresql.auth.username must be a valid PostgreSQL identifier of at most 63 characters" -}}
  {{- end -}}
  {{- if or (gt (len $database) 63) (not (regexMatch "^[A-Za-z_][A-Za-z0-9_]*$" $database)) -}}
    {{- fail "postgresql.auth.database must be a valid PostgreSQL identifier of at most 63 characters" -}}
  {{- end -}}
  {{- if not (regexMatch "^[A-Za-z0-9._~-]+$" $password) -}}
    {{- fail "postgresql.auth.password must contain only URL-safe characters: A-Z, a-z, 0-9, dot, underscore, tilde, or hyphen" -}}
  {{- end -}}
{{- end -}}
{{- end -}}
