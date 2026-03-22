FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/proxylens-proxy

COPY mitmproxy_addon /tmp/mitmproxy_addon
COPY examples/chained-apps-with-manual-propagation/proxy/run_addon.py /opt/proxylens-proxy/run_addon.py

RUN pip install --no-cache-dir /tmp/mitmproxy_addon

EXPOSE 8080

CMD ["mitmdump", "--mode", "regular", "--listen-host", "0.0.0.0", "--listen-port", "8080", "--set", "ssl_insecure=true", "-s", "/opt/proxylens-proxy/run_addon.py"]
