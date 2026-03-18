#!/usr/bin/env bash
# Generate a self-signed TLS certificate for local development / testing.
# For production, use Let's Encrypt (certbot) or your organisation's CA.
#
# Usage:
#   chmod +x deploy/generate-self-signed-cert.sh
#   ./deploy/generate-self-signed-cert.sh

set -euo pipefail

CERT_DIR="/etc/ssl/nhs-processor"
DAYS=365

echo "Creating certificate directory: ${CERT_DIR}"
sudo mkdir -p "${CERT_DIR}"

echo "Generating self-signed certificate (${DAYS} days)..."
sudo openssl req -x509 -nodes -days "${DAYS}" \
    -newkey rsa:2048 \
    -keyout "${CERT_DIR}/privkey.pem" \
    -out "${CERT_DIR}/fullchain.pem" \
    -subj "/C=GB/ST=England/L=London/O=NHS-Processor-Dev/CN=localhost"

sudo chmod 600 "${CERT_DIR}/privkey.pem"
sudo chmod 644 "${CERT_DIR}/fullchain.pem"

echo ""
echo "Certificate generated:"
echo "  Certificate: ${CERT_DIR}/fullchain.pem"
echo "  Private key: ${CERT_DIR}/privkey.pem"
echo ""
echo "For production, replace these with real certificates from Let's Encrypt:"
echo "  sudo certbot certonly --nginx -d your-domain.nhs.uk"
