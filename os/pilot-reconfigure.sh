#!/bin/bash
# PiLot OS - Re-enter setup wizard
# Installed to: /usr/lib/pilot/pilot-reconfigure.sh
# Stops dashboard, removes .setup-complete, re-enables setup service

set -euo pipefail

echo "=== PiLot OS: Reconfiguration ==="

# Stop the dashboard so port 80 is free for the setup redirect
echo "Stopping pilot-dashboard..."
systemctl stop pilot-dashboard.service || true

# Remove the setup-complete flag so ConditionPathExists allows startup
echo "Removing setup-complete marker..."
rm -f /var/lib/pilot/.setup-complete

# Re-enable and start the setup wizard
echo "Starting pilot-setup..."
systemctl enable pilot-setup.service
systemctl start pilot-setup.service

echo "=== Setup wizard is now available at http://<device-ip>:8080 ==="
