FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/proxylens

COPY server /tmp/server

RUN pip install --no-cache-dir /tmp/server

EXPOSE 8000

CMD ["proxylens-server", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "/data"]
