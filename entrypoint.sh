#!/usr/bin/env bash
set -e

# ------ 默认值 ------
BOT_URL=${BOT_URL:-}
BOT_TOKEN=${BOT_TOKEN:-}
BOT_PROTOCOL=${BOT_PROTOCOL:-napcat}
BOT_PLUGIN_DIR=${BOT_PLUGIN_DIR:-}
BOT_CONFIG_DIR=${BOT_CONFIG_DIR:-config}
BOT_DATA_DIR=${BOT_DATA_DIR:-data}

# ------ 必填校验 ------
if [[ -z "$BOT_URL" ]]; then
  echo "ERROR: 必须指定环境变量 BOT_URL（WebSocket 地址）"
  exit 1
fi

# ------ 组装命令 ------
CMD=(
  python -m src      # 模块入口
  start
  --url "$BOT_URL"
  --protocol "$BOT_PROTOCOL"
  --config-dir "$BOT_CONFIG_DIR"
  --data-dir "$BOT_DATA_DIR"
)

[[ -n "$BOT_TOKEN" ]]      && CMD+=(--token "$BOT_TOKEN")
[[ -n "$BOT_PLUGIN_DIR" ]] && CMD+=(--plugin-dir "$BOT_PLUGIN_DIR")

# ------ 启动 ------
exec "${CMD[@]}"

# # 构建（全部 ARG 都用默认值）
# docker build -t mybot:3.13 .

# # 运行（只改必要变量）
# docker run -it --rm \
#   -e BOT_URL=ws://host.docker.internal:3001 \
#   -e BOT_TOKEN=abc123 \
#   -v $PWD/config:/app/config \
#   -v $PWD/data:/app/data \
#   -v $PWD/plugins:/plugins \
#   mybot:3.13

# # 如果需要自定义 build 参数
# docker build \
#   --build-arg USER_ID=1001 \
#   --build-arg EXTRA_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
#   -t mybot:3.13 .
