#!/bin/sh
set -eu

for _ in $(seq 1 50); do
    if [ -f /mitmproxy/mitmproxy-ca-cert.pem ] || [ ! -d /mitmproxy ]; then
        break
    fi
    sleep 0.1
done

updated=0

if [ -f /mitmproxy/mitmproxy-ca-cert.pem ]; then
    cp /mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/proxylens-mitmproxy-ca.crt
    updated=1
fi

if [ -f /certs/localhost.crt ]; then
    cp /certs/localhost.crt /usr/local/share/ca-certificates/proxylens-localhost.crt
    updated=1
fi

if [ "$updated" -eq 1 ]; then
    update-ca-certificates >/dev/null 2>&1
fi

exec dotnet /app/app2.dll
