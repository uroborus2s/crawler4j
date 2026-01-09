#!/bin/bash
set -e

# 获取脚本所在目录的上一级目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 开始构建文档..."
# 使用 uv 运行构建
uv run mkdocs build

echo "📦 构建完成。准备上传..."

# 默认配置，可修改或通过环境变量传入
REMOTE_HOST=${DEPLOY_HOST:-"db.whzhsc.cn"}
REMOTE_USER=${DEPLOY_USER:-"root"}
REMOTE_DIR=${DEPLOY_DIR:-"/var/www/crawler"}

echo "📤 上传到 $REMOTE_HOST:$REMOTE_DIR ..."
# 强制使用 scp，避免远程服务器未安装 rsync 导致的错误
echo "使用 scp 上传..."
scp -r site/* "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}"

echo "✅ 部署完成！"
echo "🌐 访问地址: http://crawler.urobrous.cn"
