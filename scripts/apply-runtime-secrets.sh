#!/usr/bin/env bash
set -euo pipefail

project_root="${RUNBOOKIQ_ROOT:-${HOME}/runbookiq}"
staged_env="${1:-}"
shared_env="${project_root}/shared/.env"
temporary_env=""
remove_staged=false

cleanup() {
  if [[ -n "${temporary_env}" ]] && [[ -f "${temporary_env}" ]]; then
    rm -f -- "${temporary_env}"
  fi
  if [[ "${remove_staged}" == "true" ]] && [[ -f "${staged_env}" ]]; then
    rm -f -- "${staged_env}"
  fi
}
trap cleanup EXIT

if [[ ! -f "${staged_env}" ]]; then
  echo "Staged runtime configuration does not exist." >&2
  exit 1
fi
if [[ ! -f "${shared_env}" ]]; then
  echo "Production environment file does not exist." >&2
  exit 1
fi

staged_env="$(realpath "${staged_env}")"
case "${staged_env}" in
  "${project_root}/inbox/"*) ;;
  *)
    echo "Staged runtime configuration must be inside ${project_root}/inbox." >&2
    exit 1
    ;;
esac
remove_staged=true

declare -A values=()
while IFS='=' read -r key value || [[ -n "${key}${value}" ]]; do
  key="${key%$'\r'}"
  value="${value%$'\r'}"
  case "${key}" in
    RUNBOOKIQ_TURNSTILE_SITE_KEY|RUNBOOKIQ_TURNSTILE_SECRET_KEY|RUNBOOKIQ_TURNSTILE_REQUIRED)
      if [[ -n "${values[${key}]+present}" ]]; then
        echo "Duplicate runtime configuration key: ${key}" >&2
        exit 1
      fi
      values["${key}"]="${value}"
      ;;
    "") ;;
    *)
      echo "Unsupported runtime configuration key: ${key}" >&2
      exit 1
      ;;
  esac
done < "${staged_env}"

site_key="${values[RUNBOOKIQ_TURNSTILE_SITE_KEY]:-}"
secret_key="${values[RUNBOOKIQ_TURNSTILE_SECRET_KEY]:-}"
required="${values[RUNBOOKIQ_TURNSTILE_REQUIRED]:-}"

if [[ ! "${site_key}" =~ ^0x[A-Za-z0-9_-]{20,}$ ]]; then
  echo "Turnstile site key has an invalid format." >&2
  exit 1
fi
if [[ ! "${secret_key}" =~ ^0x[A-Za-z0-9_-]{30,}$ ]]; then
  echo "Turnstile secret key has an invalid format." >&2
  exit 1
fi
if [[ "${required}" != "true" ]]; then
  echo "Turnstile must be required in production." >&2
  exit 1
fi

temporary_env="$(mktemp "${project_root}/shared/.env.XXXXXX")"
chmod 600 "${temporary_env}"

while IFS= read -r line || [[ -n "${line}" ]]; do
  line="${line%$'\r'}"
  case "${line}" in
    RUNBOOKIQ_TURNSTILE_SITE_KEY=*|RUNBOOKIQ_TURNSTILE_SECRET_KEY=*|RUNBOOKIQ_TURNSTILE_REQUIRED=*)
      continue
      ;;
  esac
  printf '%s\n' "${line}" >> "${temporary_env}"
done < "${shared_env}"

{
  printf 'RUNBOOKIQ_TURNSTILE_SITE_KEY=%s\n' "${site_key}"
  printf 'RUNBOOKIQ_TURNSTILE_SECRET_KEY=%s\n' "${secret_key}"
  printf 'RUNBOOKIQ_TURNSTILE_REQUIRED=true\n'
} >> "${temporary_env}"

mv -f -- "${temporary_env}" "${shared_env}"
temporary_env=""
chmod 600 "${shared_env}"

echo "Production Turnstile configuration updated."
