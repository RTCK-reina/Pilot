#!/bin/bash -e
#
# Stage: 00-install-deps
# Install system packages and enable mDNS (pilot.local)
#

on_chroot << 'CHEOF'

# Install packages listed in the packages file (handled by pi-gen automatically),
# then enable avahi-daemon so the device is reachable as pilot.local via mDNS.
systemctl enable avahi-daemon

# Ensure nftables is enabled for the firewall
systemctl enable nftables

CHEOF
