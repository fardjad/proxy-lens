FROM oven/bun:1 AS ui-builder

WORKDIR /src/ui

COPY ui /src/ui

ARG PUBLIC_PROXYLENS_BASE_URL=http://127.0.0.1:8000
ENV PUBLIC_PROXYLENS_BASE_URL=${PUBLIC_PROXYLENS_BASE_URL}

RUN bun install --frozen-lockfile
RUN bun run build

FROM debian:stable-slim AS bundle

WORKDIR /proxy-lens

COPY --from=ui-builder /src/ui/dist /proxy-lens/ui
COPY server /proxy-lens/server
COPY docker/proxy-lens/Caddyfile /proxy-lens/Caddyfile
COPY docker/proxy-lens/bin /proxy-lens/bin

RUN chmod +x /proxy-lens/bin/*.sh


FROM python:3-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PROXYLENS_SERVER_PORT=8000
ENV PROXYLENS_SERVER_DATA_DIR=/data
ENV PROXYLENS_UI_PORT=8080

WORKDIR /proxy-lens

COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy
COPY --from=bundle /proxy-lens /proxy-lens

RUN python -m pip install --no-cache-dir /proxy-lens/server
RUN mkdir -p /data

EXPOSE 8000 8080

ENTRYPOINT ["/proxy-lens/bin/run.sh"]
