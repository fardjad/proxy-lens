#!/bin/sh
set -eu

bundle=/tmp/proxylens-extra-ca.pem
rm -f "$bundle"
touch "$bundle"

for _ in $(seq 1 50); do
    if [ -f /mitmproxy/mitmproxy-ca-cert.pem ] || [ ! -d /mitmproxy ]; then
        break
    fi
    sleep 0.1
done

if [ -f /mitmproxy/mitmproxy-ca-cert.pem ]; then
    cat /mitmproxy/mitmproxy-ca-cert.pem >>"$bundle"
fi

if [ -f /certs/localhost.crt ]; then
    cat /certs/localhost.crt >>"$bundle"
fi

if [ -s "$bundle" ]; then
    export NODE_EXTRA_CA_CERTS="$bundle"
fi

exec node /app/app.js
