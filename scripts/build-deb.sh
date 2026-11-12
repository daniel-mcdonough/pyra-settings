#!/bin/sh
#
# build-deb.sh: build the .deb in a clean Debian trixie container, so the result doesn't depend on the build
# machine. The package is Architecture: all, so any host can build it.
#
#   scripts/build-deb.sh      leaves pyra-settings_<version>_all.deb in dist/ and prints dpkg -c and lintian
#
# Needs docker. On a Debian machine, dpkg-buildpackage -us -uc -b works too.
#
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
docker run --rm -e DEBIAN_FRONTEND=noninteractive \
	-v "$PWD:/src:ro" -v "$PWD/dist:/out" debian:trixie sh -euc '
	apt-get update -qq
	apt-get install -y -qq --no-install-recommends build-essential debhelper lintian desktop-file-utils >/dev/null
	# Build from a copy of the tracked tree: dpkg-buildpackage writes into and next to it, and the checkout is
	# mounted read-only.
	mkdir /build
	cp -r /src /build/pyra-settings
	cd /build/pyra-settings
	rm -rf dist
	desktop-file-validate data/pyra-settings.desktop
	dpkg-buildpackage -us -uc -b
	dpkg -c ../*.deb
	lintian --info ../*.changes || true
	cp ../*.deb /out/
	chown '"$(id -u):$(id -g)"' /out/*.deb
'
ls -l dist/
