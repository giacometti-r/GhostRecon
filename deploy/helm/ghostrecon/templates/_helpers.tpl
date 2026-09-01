{{- define "ghostrecon.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "ghostrecon.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := include "ghostrecon.name" . }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end -}}

{{- define "ghostrecon.postgresql.fullname" -}}
{{- printf "%s-postgresql" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "ghostrecon.redis.fullname" -}}
{{- printf "%s-redis" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "ghostrecon.labels" -}}
app.kubernetes.io/name: {{ include "ghostrecon.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "ghostrecon.image" -}}
{{- if .Values.image.digest -}}
{{ printf "%s@%s" .Values.image.repository .Values.image.digest }}
{{- else -}}
{{ printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end -}}
{{- end -}}

{{- define "ghostrecon.projectSecrets" -}}
{{- $root := index . 0 -}}
{{- $service := index . 1 -}}
{{- range (index $root.Values.secretProjection $service | default list) }}
- name: {{ . }}
  valueFrom:
    secretKeyRef:
      name: ghostrecon-secrets
      key: {{ . }}
      optional: true
{{- end -}}
{{- end -}}

{{- define "ghostrecon.validate" -}}
{{- $profile := required "profile is required" .Values.profile -}}
{{- if not (has $profile (list "local" "test" "staging" "production")) -}}
{{- fail "profile must be one of local, test, staging, production" -}}
{{- end -}}
{{- $strict := or (eq $profile "staging") (eq $profile "production") -}}
{{- if $strict -}}
  {{- if .Values.localOIDC.enabled -}}
    {{- fail "localOIDC.enabled must be false in staging/production" -}}
  {{- end -}}
  {{- if not .Values.ingress.enabled -}}
    {{- fail "ingress.enabled must be true in staging/production" -}}
  {{- end -}}
  {{- $_ := required "ingress.tlsSecretName is required in staging/production" .Values.ingress.tlsSecretName -}}
  {{- if ne (get .Values.env "GHOSTRECON_DOCS_ENABLED" | default "true") "false" -}}
    {{- fail "env.GHOSTRECON_DOCS_ENABLED must be false in staging/production" -}}
  {{- end -}}
  {{- if ne (get .Values.env "GHOSTRECON_AUTHENTICATION_BACKEND" | default "") "oidc" -}}
    {{- fail "env.GHOSTRECON_AUTHENTICATION_BACKEND must be oidc in staging/production" -}}
  {{- end -}}
  {{- $digestPattern := "^sha256:[a-f0-9]{64}$" -}}
  {{- if not (regexMatch $digestPattern (.Values.image.digest | default "")) -}}
    {{- fail "image.digest must be a SHA-256 digest in staging/production" -}}
  {{- end -}}
  {{- if eq (.Values.image.tag | default "") "latest" -}}
    {{- fail "image.tag must not be latest in staging/production" -}}
  {{- end -}}
  {{- if .Values.postgresql.enabled -}}
    {{- if not (regexMatch $digestPattern (.Values.postgresql.image.digest | default "")) -}}
      {{- fail "postgresql.image.digest must be a SHA-256 digest in staging/production" -}}
    {{- end -}}
    {{- if eq (.Values.postgresql.image.tag | default "") "latest" -}}
      {{- fail "postgresql.image.tag must not be latest in staging/production" -}}
    {{- end -}}
  {{- end -}}
  {{- if .Values.redis.enabled -}}
    {{- if not (regexMatch $digestPattern (.Values.redis.image.digest | default "")) -}}
      {{- fail "redis.image.digest must be a SHA-256 digest in staging/production" -}}
    {{- end -}}
    {{- if eq (.Values.redis.image.tag | default "") "latest" -}}
      {{- fail "redis.image.tag must not be latest in staging/production" -}}
    {{- end -}}
  {{- end -}}
  {{- if .Values.emailVerifier.enabled -}}
    {{- if not (regexMatch $digestPattern (.Values.emailVerifier.image.digest | default "")) -}}
      {{- fail "emailVerifier.image.digest must be a SHA-256 digest in staging/production" -}}
    {{- end -}}
    {{- if eq (.Values.emailVerifier.image.tag | default "") "latest" -}}
      {{- fail "emailVerifier.image.tag must not be latest in staging/production" -}}
    {{- end -}}
  {{- end -}}
  {{- $liveProviders := dict "GHOSTRECON_GEOCODER_PROVIDER" "nominatim" "GHOSTRECON_SEARCH_PROVIDER" "openserp" "GHOSTRECON_NEWS_PROVIDER" "serpapi" "GHOSTRECON_EMAIL_VERIFIER_PROVIDER" "http" "GHOSTRECON_CRM_PROVIDER" "attio" "GHOSTRECON_CALENDAR_PROVIDER" "google" "GHOSTRECON_SMTP_PROVIDER" "smtp" "GHOSTRECON_IMAP_PROVIDER" "imap" -}}
  {{- range $key, $expected := $liveProviders -}}
    {{- if ne (get $.Values.env $key | default "") $expected -}}
      {{- fail (printf "env.%s must be %s in staging/production" $key $expected) -}}
    {{- end -}}
  {{- end -}}
  {{- range $key := list "GHOSTRECON_ATTIO_ACCESS_TOKEN" "GHOSTRECON_SERPAPI_API_KEY" "GHOSTRECON_GOOGLE_PRIVATE_KEY" "GHOSTRECON_SMTP_PASSWORD" "GHOSTRECON_IMAP_PASSWORD" -}}
    {{- $value := required (printf "secretEnv.%s is required in staging/production" $key) (get $.Values.secretEnv $key) -}}
    {{- if regexMatch "(?i)^replace[_-]" ($value | toString) -}}
      {{- fail (printf "secretEnv.%s must not be a placeholder" $key) -}}
    {{- end -}}
  {{- end -}}
  {{- range $key := list "GHOSTRECON_GOOGLE_CALENDAR_ID" "GHOSTRECON_GOOGLE_CLIENT_EMAIL" "GHOSTRECON_SMTP_HOST" "GHOSTRECON_SMTP_USERNAME" "GHOSTRECON_SMTP_FROM_ADDRESS" "GHOSTRECON_IMAP_HOST" "GHOSTRECON_IMAP_USERNAME" "GHOSTRECON_NOMINATIM_USER_AGENT" "GHOSTRECON_CRAWL_USER_AGENT" -}}
    {{- $value := required (printf "env.%s is required in staging/production" $key) (get $.Values.env $key) -}}
    {{- if regexMatch "(?i)^replace[_-]" ($value | toString) -}}
      {{- fail (printf "env.%s must not be a placeholder" $key) -}}
    {{- end -}}
  {{- end -}}
  {{- if contains "example.com" (get .Values.env "GHOSTRECON_NOMINATIM_USER_AGENT" | default "") -}}
    {{- fail "env.GHOSTRECON_NOMINATIM_USER_AGENT must identify the operator" -}}
  {{- end -}}
  {{- if contains "example.com" (get .Values.env "GHOSTRECON_CRAWL_USER_AGENT" | default "") -}}
    {{- fail "env.GHOSTRECON_CRAWL_USER_AGENT must identify the operator" -}}
  {{- end -}}
  {{- if contains "@example." (get .Values.env "GHOSTRECON_SMTP_FROM_ADDRESS" | default "") -}}
    {{- fail "env.GHOSTRECON_SMTP_FROM_ADDRESS must not be an example address" -}}
  {{- end -}}
{{- end -}}
{{- end -}}
