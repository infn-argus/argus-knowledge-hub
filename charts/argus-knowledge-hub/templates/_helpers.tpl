{{- define "argus.labels" -}}
app.kubernetes.io/part-of: argus-knowledge-hub
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "argus.secretEnv" -}}
- name: {{ .name }}
  valueFrom:
    secretKeyRef:
      name: {{ .secret }}
      key: {{ .key }}
{{- end }}

{{/* The API's environment, shared by the API and the portability jobs. */}}
{{- define "argus.apiEnv" -}}
{{- $kcIssuer := printf "https://%s/realms/%s" .Values.hosts.keycloak .Values.keycloak.realm -}}
{{- $providers := .Values.api.extraProviders -}}
{{ include "argus.secretEnv" (dict "name" "DATABASE_URL" "secret" .Values.existingSecret "key" "database-url") }}
{{ include "argus.secretEnv" (dict "name" "TOKEN_PEPPER" "secret" .Values.existingSecret "key" "token-pepper") }}
{{ include "argus.secretEnv" (dict "name" "IMPORT_SECRETS_KEY" "secret" .Values.existingSecret "key" "import-secrets-key") }}
- {name: ATTACHMENTS_DIR, value: /data/attachments}
- {name: ARGUS_PORTABILITY_ROOT, value: /data/portability}
- {name: ARGUS_PORTABILITY_DECRYPTION_KEYS, value: /etc/argus/portability-decryption}
{{- if .Values.keycloak.enabled }}
# The issuer is the public address the browser signs in at; the keys are fetched inside the cluster.
- {name: OIDC_ISSUER, value: {{ $kcIssuer | quote }}}
- {name: OIDC_JWKS_URI, value: "http://argus-keycloak:8080/realms/{{ .Values.keycloak.realm }}/protocol/openid-connect/certs"}
- {name: OIDC_AUDIENCE, value: {{ .Values.keycloak.clientId | quote }}}
{{- end }}
{{- with $providers }}
- name: OIDC_EXTRA_PROVIDERS
  value: {{ toJson . | quote }}
{{- end }}
{{- range $k, $v := .Values.api.env }}
- {name: {{ $k }}, value: {{ $v | quote }}}
{{- end }}
{{- end }}
