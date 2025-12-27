# ---------- 1. 基础镜像（可重定义） ----------
ARG PY_BASE=python:3.13-slim
FROM ${PY_BASE} AS builder

# ---------- 2. 用户可配参数 ----------
ARG USER_ID=1000
ARG GROUP_ID=1000
ARG USER_NAME=appuser
ARG APP_PORT=8000
ARG REQUIREMENTS=requirements.txt
ARG EXTRA_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""

# ---------- 3. 构建时环境 ----------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_EXTRA_INDEX_URL=${EXTRA_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

# ---------- 4. 系统依赖（附加指令区 ①） ----------
# <<< 附加指令：builder 系统包开始 >>>
# 例：RUN apt-get update && apt-get install -y --no-install-recommends \
#        build-essential libpq-dev \
#     && rm -rf /var/lib/apt/lists/*
# <<< 附加指令：builder 系统包结束 >>>

# ---------- 5. 创建用户 ----------
RUN groupadd -g ${GROUP_ID} ${USER_NAME} && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash ${USER_NAME}

# ---------- 6. 依赖安装 ----------
WORKDIR /build
COPY ${REQUIREMENTS} ./
# <<< 附加指令：pip 安装前开始（附加指令区 ②） >>>
# <<< 附加指令：pip 安装前结束 >>>
RUN pip install -r ${REQUIREMENTS}
# <<< 附加指令：pip 安装后开始（附加指令区 ③） >>>
# 例：RUN pip install gunicorn==23.0.0
# <<< 附加指令：pip 安装后结束 >>>

# ---------- 7. 运行时镜像 ----------
FROM ${PY_BASE} AS runtime

# 把 ARG 重新声明一遍，以便在 runtime 阶段使用
ARG USER_ID=1000
ARG GROUP_ID=1000
ARG USER_NAME=appuser
ARG APP_PORT=8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/${USER_NAME}/.local/bin:$PATH \
    APP_PORT=${APP_PORT}

# ---------- 8. 运行时系统依赖（附加指令区 ④） ----------
# <<< 附加指令：runtime 系统包开始 >>>
# 例：RUN apt-get update && apt-get install -y --no-install-recommends \
#        curl \
#     && rm -rf /var/lib/apt/lists/*
# <<< 附加指令：runtime 系统包结束 >>>

# 复制用户与依赖
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
RUN groupadd -g ${GROUP_ID} ${USER_NAME} && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash ${USER_NAME}

# ---------- 9. 应用代码 ----------
WORKDIR /app
COPY --chown=${USER_NAME}:${USER_NAME} . .

# ---------- 10. 复制入口脚本并赋权 ----------
COPY --chown=${USER_NAME}:${USER_NAME} entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ---------- 11. 健康检查（附加指令区 ⑤） ----------
# <<< 附加指令：健康检查开始 >>>
# 例：HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
#     CMD python -c "print('ok')" || exit 1
# <<< 附加指令：健康检查结束 >>>

USER ${USER_NAME}
EXPOSE ${APP_PORT}

# ---------- 12. 默认启动命令 ----------
ENTRYPOINT ["/entrypoint.sh"]
# 如果想额外加 CMD 参数，可写在下面（附加指令区 ⑥）
# <<< 附加指令：CMD 开始 >>>
# CMD ["--some-extra-flag"]
# <<< 附加指令：CMD 结束 >>>
