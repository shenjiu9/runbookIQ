#!/usr/bin/env bash
set -euo pipefail

project_root="${RUNBOOKIQ_ROOT:-${HOME}/runbookiq}"
archive="${1:-}"
version="${2:-}"
shared_env="${project_root}/shared/.env"

if [[ ! "${version}" =~ ^[0-9a-f]{7,64}$ ]]; then
  echo "版本必须是 7-64 位十六进制 Git commit SHA" >&2
  exit 1
fi
if [[ ! -f "${archive}" ]]; then
  echo "发布包不存在：${archive}" >&2
  exit 1
fi
if [[ ! -f "${shared_env}" ]]; then
  echo "生产环境文件不存在：${shared_env}" >&2
  exit 1
fi

archive="$(realpath "${archive}")"
case "${archive}" in
  "${project_root}/inbox/"*) ;;
  *)
    echo "发布包必须位于 ${project_root}/inbox" >&2
    exit 1
    ;;
esac

release_dir="${project_root}/releases/${version}"
temporary_dir="${release_dir}.partial"
current_link="${project_root}/current"
previous_release=""
if [[ -L "${current_link}" ]]; then
  previous_release="$(realpath "${current_link}")"
fi

exec 9>"${project_root}/deploy.lock"
flock -n 9 || {
  echo "已有另一个发布正在执行" >&2
  exit 1
}

rm -rf -- "${temporary_dir}"
mkdir -p -- "${temporary_dir}"
tar -xzf "${archive}" -C "${temporary_dir}"
test -f "${temporary_dir}/docker-compose.yml"
rm -rf -- "${release_dir}"
mv -- "${temporary_dir}" "${release_dir}"

compose=(
  docker compose
  --env-file "${shared_env}"
  -f "${release_dir}/docker-compose.yml"
)

RUNBOOKIQ_RELEASE="${version}" "${compose[@]}" config --quiet
RUNBOOKIQ_RELEASE="${version}" "${compose[@]}" run --rm --no-deps caddy \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
RUNBOOKIQ_RELEASE="${version}" "${compose[@]}" build
RUNBOOKIQ_RELEASE="${version}" "${compose[@]}" up -d --remove-orphans

app_port="$(
  sed -n 's/^APP_PORT=//p' "${shared_env}" |
    tail -1 |
    tr -d '\r'
)"
app_port="${app_port:-8080}"

healthy=false
for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${app_port}/api/health" >/dev/null; then
    healthy=true
    break
  fi
  sleep 5
done

if [[ "${healthy}" != true ]]; then
  echo "新版本健康检查失败，正在恢复上一版本" >&2
  if [[ -n "${previous_release}" ]] && [[ -f "${previous_release}/docker-compose.yml" ]]; then
    previous_version="$(basename "${previous_release}")"
    RUNBOOKIQ_RELEASE="${previous_version}" docker compose \
      --env-file "${shared_env}" \
      -f "${previous_release}/docker-compose.yml" \
      up -d --remove-orphans
  fi
  exit 1
fi

rm -f -- "${current_link}.next"
ln -s "${release_dir}" "${current_link}.next"
mv -Tf "${current_link}.next" "${current_link}"
rm -f -- "${archive}"

echo "RunbookIQ ${version} 已发布，健康检查通过。"
