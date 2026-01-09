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

# === 部署流程适配 Sudo 用户 ===
TEMP_REMOTE_DIR="/tmp/crawler_docs_$(date +%s)"

echo "1️⃣  [远程] 创建临时目录: $TEMP_REMOTE_DIR"
# 确保临时目录存在
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p $TEMP_REMOTE_DIR"

echo "2️⃣  [上传] 传输文件到临时目录..."
# 上传构建产物到临时目录 (不需要 root 权限)
scp -r site/* "${REMOTE_USER}@${REMOTE_HOST}:$TEMP_REMOTE_DIR"

echo "3️⃣  [部署] 使用 sudo 移动文件到目标目录..."
# 使用 ssh -t 强制分配伪终端，以便 sudo 能弹出密码提示
# 逻辑：确保目标目录存在 -> 复制文件 -> 清理临时目录
ssh -t "${REMOTE_USER}@${REMOTE_HOST}" "sudo mkdir -p $REMOTE_DIR && sudo cp -r $TEMP_REMOTE_DIR/* $REMOTE_DIR/ && sudo rm -rf $TEMP_REMOTE_DIR"

echo "✅ 部署完成！"
echo "🌐 访问地址: http://${REMOTE_HOST}"
