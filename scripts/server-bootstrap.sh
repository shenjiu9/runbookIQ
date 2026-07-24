#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 运行：sudo bash scripts/server-bootstrap.sh <deploy-user>" >&2
  exit 1
fi

deploy_user="${1:-}"
if [[ -z "${deploy_user}" ]] || ! id "${deploy_user}" >/dev/null 2>&1; then
  echo "必须传入已存在的部署用户，例如：shenjiu" >&2
  exit 1
fi

deploy_home="$(getent passwd "${deploy_user}" | cut -d: -f6)"
project_root="${deploy_home}/runbookiq"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker "${deploy_user}"

install -d -m 0750 -o "${deploy_user}" -g "${deploy_user}" \
  "${project_root}" \
  "${project_root}/bin" \
  "${project_root}/inbox" \
  "${project_root}/releases" \
  "${project_root}/shared"
install -m 0750 -o "${deploy_user}" -g "${deploy_user}" \
  "${script_dir}/deploy-release.sh" \
  "${project_root}/bin/deploy-release.sh"

echo
echo "Docker 与发布目录已配置完成。"
echo "请退出当前 SSH 会话后重新登录，使 docker 用户组生效。"
