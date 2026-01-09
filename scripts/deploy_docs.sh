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
REMOTE_DIR=${DEPLOY_DIR:-"/var/www/crawler"}

echo "📤 上传到 $REMOTE_HOST:$REMOTE_DIR ..."
# 使用 rsync 进行增量同步（比 scp 更高效），如果没有 rsync 则回退到 scp
if command -v rsync &> /dev/null; then
    # -a: archive mode, -v: verbose, -z: compress, --delete: 删除目标端多余文件
    rsync -avz --delete site/ "$REMOTE_HOST:$REMOTE_DIR"
else
    echo "⚠️ 未找到 rsync，使用 scp... (建议安装 rsync 以提高速度)"
    scp -r site/* "$REMOTE_HOST:$REMOTE_DIR"
fi

echo "✅ 部署完成！"
echo "🌐 访问地址: http://crawler.urobrous.cn"
