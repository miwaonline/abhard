#!/bin/bash
ABHARD_PKG_VERSION=3.0.0-1
# Create necessary directories
mkdir -p debian
mkdir -p opt/abhard/{abhard,etc,cert,keys,templates}
mkdir -p usr/lib/systemd/system

# Place your files into the respective directories
cp ../abhard/*py opt/abhard/abhard/
cp ../abhard/_EUSignCP.so opt/abhard/abhard/
cp ../cert/* opt/abhard/cert/
cp ../etc/abhard.yml* opt/abhard/etc/
cp ../templates/* opt/abhard/templates/
cp ../lib/* usr/lib/

# Create the abhard.service file
echo "[Unit]
Description=Abhard Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/abhard/abhard/app.py
User=nobody
Group=nogroup
Environment=PYTHONUNBUFFERED=1
Environment=LD_LIBRARY_PATH=/opt/abhard/lib
WorkingDirectory=/opt/abhard
RestartSec=10
Restart=on-failure

[Install]
WantedBy=multi-user.target" > usr/lib/systemd/system/abhard.service

# Create debian control files
echo "Source: abhard
Section: misc
Priority: optional
Maintainer: Mykhailo Masyk <mykhailo.masyk@gmail.com>
Standards-Version: 4.1.5
Build-Depends: debhelper (>= 11)

Package: abhard
Architecture: any
Depends: \${shlibs:Depends}, \${misc:Depends}, python3-simplejson, python3-flask, systemd, python3-yaml, python3-requests, python3-waitress
Description: Abhard package
 This package installs Abhard software." > debian/control

echo "opt/abhard
opt/abhard/abhard
opt/abhard/etc
opt/abhard/cert
opt/abhard/keys
opt/abhard/templates
usr/lib/systemd/system
var/log/abhard" > debian/dirs

echo "opt/abhard/abhard/* opt/abhard/abhard/
opt/abhard/etc/* opt/abhard/etc/
opt/abhard/templates/* opt/abhard/templates/
usr/lib/* usr/lib/
usr/lib/systemd/system/abhard.service usr/lib/systemd/system/" > debian/install

echo "/opt/abhard/etc/abhard.yml" > debian/conffiles

# Create the postinst script
echo "#!/bin/bash
set -e
pip3 install python-escpos
systemctl daemon-reload
systemctl enable abhard.service
systemctl start abhard.service" > debian/postinst
chmod 755 debian/postinst

# Create the prerm script
echo "#!/bin/bash
set -e

systemctl stop abhard.service
systemctl disable abhard.service" > debian/prerm
chmod 755 debian/prerm

# Create the changelog file
echo "abhard ($ABHARD_PKG_VERSION) unstable; urgency=low

  * Completely rewritten release.

 -- Mykhailo Masyk <Mykhailo.Masyk@gmail.com>  Tue, 09 Jul 2024 00:00:00 +0000" > debian/changelog

# Create the rules file
echo "#!/usr/bin/make -f

%:
	dh \$@" > debian/rules
chmod 755 debian/rules

# Create the compat file
echo "12" > debian/compat

# Build the package
dpkg-buildpackage -us -uc

# Clean up
rm -rf debian/
rm -rf opt/
rm -rf usr/
rm -f ../abhard_${ABHARD_PKG_VERSION}_amd64.buildinfo
rm -f ../abhard_${ABHARD_PKG_VERSION}_amd64.changes
rm -f ../abhard_${ABHARD_PKG_VERSION}.dsc
rm -f ../abhard_${ABHARD_PKG_VERSION}.tar.gz
rm -f ../abhard-dbgsym_${ABHARD_PKG_VERSION}_amd64.ddeb
# Test the package; uncomment once ready
# piuparts abhard.deb
