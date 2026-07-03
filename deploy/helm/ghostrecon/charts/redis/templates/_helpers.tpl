{{- define "redis.fullname" -}}
{{- printf "%s-redis" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end -}}

{{- define "redis.labels" -}}
app.kubernetes.io/name: redis
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: redis
{{- end -}}

{{- define "redis.selectorLabels" -}}
app.kubernetes.io/name: redis
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: redis
{{- end -}}

{{- define "redis.validate" -}}
{{- if .Values.enabled -}}
  {{- $password := required "redis.auth.password is required; provide it through the SOPS values file" .Values.auth.password -}}
  {{- if not (regexMatch "^[A-Za-z0-9._~-]+$" $password) -}}
    {{- fail "redis.auth.password must contain only URL-safe characters: A-Z, a-z, 0-9, dot, underscore, tilde, or hyphen" -}}
  {{- end -}}
{{- end -}}
{{- end -}}
