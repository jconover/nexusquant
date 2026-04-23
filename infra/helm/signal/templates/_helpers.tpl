{{/* vim: set filetype=mustache: */}}

{{- define "signal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "signal.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "signal.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "signal.labels" -}}
helm.sh/chart: {{ include "signal.chart" . }}
{{ include "signal.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: signal
app.kubernetes.io/part-of: nexusquant
{{- end }}

{{- define "signal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "signal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "signal.imageRef" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion -}}
{{ .Values.image.repository }}:{{ $tag }}
{{- end }}

{{- define "signal.alpacaSecretName" -}}
{{ include "signal.fullname" . }}-alpaca
{{- end }}

{{- define "signal.postgresSecretName" -}}
{{ include "signal.fullname" . }}-postgres
{{- end }}
