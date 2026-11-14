#!/bin/sh
#
# install-on-pyra.sh: copy the newest .deb in dist/ to the Pyra and install it with apt (docs/testing.md).
#
#   scripts/install-on-pyra.sh <user@host>     or     PYRA_HOST=<user@host> scripts/install-on-pyra.sh
#
# Build first with scripts/build-deb.sh. sudo on the Pyra asks for the password in this terminal.
#
set -eu
cd "$(dirname "$0")/.."

host=${1:-${PYRA_HOST:-}}
if [ -z "$host" ]; then
	echo "usage: $0 <user@host>   (or set PYRA_HOST)" >&2
	exit 2
fi

deb=$(ls dist/pyra-settings_*_all.deb 2>/dev/null | sort -V | tail -n 1)
if [ -z "$deb" ]; then
	echo "no .deb in dist/; run scripts/build-deb.sh first" >&2
	exit 1
fi
name=$(basename "$deb")

echo "installing $name on $host"
scp "$deb" "$host:/tmp/$name"
ssh -t "$host" "sudo apt-get install -y --reinstall /tmp/$name && rm -f /tmp/$name && dpkg-query -W pyra-settings"
