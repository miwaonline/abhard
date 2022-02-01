#!/bin/bash

print_usage()
{
  echo -e "
This script installs Abhard software and accepts the following parameters:

-n, --nosoft - dont install dependant software packages
-c, --nocert - dont update certificates
-l, --nolibs - dont update service libraries
-v, --version - version of the abhard to install
-u, --dbuser - database user, 'sysdba' by default
-p, --dbpass - database password, 'masterkey' by default
-d, --dbname - database name, 'abacus' by default
-s, --dbhost - database server, 'localhost' by default
-h, --help or without params - print this text

Examples:

$0 --version=1.0 --nosoft -l
    Install Abhard version 1.0, do not install dependant software and libraries

$0 --version=latest
    Install the latest available Abhard and all the necessities

Possible version values: stable, latest    
"
}


# Install dependancies (python, all the modules, wget)
install_deps()
{
  echo "Install dependant Debian packages"
  apt update -y
  apt install -y python3 python3-pip wget unzip ca-certificates libfbclient2
  echo "Install dependant Python modules"
  pip3 install cherrypy fdb simplejson lxml requests pytz pyyaml
  arch=`uname -m`
  if [ $arch == 'i686' ] ; then
    echo "Provide symlink to python3.5 for the crypto lib"
    cd /usr/lib/i386-linux-gnu
    ln -s libpython3.9.so.1.0 libpython3.5m.so.1.0
  fi
}

# Download appropriate crypto libs
install_libs()
{
  arch=`uname -m`
  if [ $arch == 'x86_64' ] ; then arch='64'; fi
  if [ $arch == 'x86_32' ] ; then arch='32'; fi
  if [ $arch == 'i686' ] ; then arch='32'; fi
  tmpfile=/tmp/eusigncp.zip
  echo "Download libraries for the $arch-bit architecture"
  wget "https://abacus.in.ua/files/abhard/eusigncp-$arch.zip" -O $tmpfile
  mkdir -p /opt/abhard
  unzip -o $tmpfile -d /opt/abhard/
  rm -f $tmpfile
}

# Download and install certificates
install_cert()
{
  echo "Install certificates"
  tmpfile=/tmp/cert.zip
  wget "https://abacus.in.ua/files/abhard/cert.zip" -O $tmpfile
  mkdir -p /opt/abhard
  unzip -o $tmpfile -d /opt/abhard/
  rm -f $tmpfile
}

# Download abhard and put it into "/opt"
# Make generic config if needed
# Configure and run systemd unit
install_abhard()
{
  echo "Downloading abhard version $1"
  tmpfile=/tmp/abhard.zip
  abhardcfg=/opt/abhard/etc/abhard.yml
  abhardunit=/lib/systemd/system/abhard.service
  wget "https://abacus.in.ua/files/abhard/abhard-$1.zip" -O $tmpfile
  mkdir -p /opt/abhard/etc
  unzip -o $tmpfile -d /opt/abhard/
  rm -f $tmpfile
  if [ ! -f $abhardcfg ] ; then
    cat << _EOF_ > $abhardcfg
database:
  user: $DBUSER
  pass: $DBPASS
  host: $DBHOST
  name: $DBNAME
webservice:
  port: 8080
rro:
  textfile:
    - name: "file1"
      filename: "/var/log/abhard-log1.log"
    - name: "file2"
      filename: "/var/log/abhard-log2.log"
  eusign_disabled:
    - name: "prro1"
      keyfile: "/home/user/keys/1234567890_1234567890_P123456789012.ZS2"
      keypass: '1234'
      rroid: '1'
_EOF_

  fi
  if [ ! -f $abhardunit ] ; then
    cat << _EOF_ > $abhardunit
[Unit]
Description=Abacus hardware adapter
After=multi-user.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
Environment=LD_LIBRARY_PATH=/opt/abhard/lib
WorkingDirectory=/opt/abhard
ExecStart=/usr/bin/python3 /opt/abhard/src/abhard.py

[Install]
WantedBy=multi-user.target
_EOF_

    systemctl daemon-reload
  fi
  systemctl restart abhard
  systemctl enable abhard
}

parse_args()
{
ARGS=`getopt -n 'Abacus' -o v:u:p:d:s:nclh \
  --longoptions version:,dbuser:,dbpass:,dbname:,dbhost:,nosoft,nocert,nolibs,help \
  -- "$@"`

if [ $? != 0 ] ; then
  echo "Internal error while parsing arguments. Script terminated." >&2 ; exit 1 ; fi

eval set -- "$ARGS"
while true ; do
    case "$1" in
        -v|--version)  VERNUMB=$2 ; shift 2 ;;
        -c|--nocert)   NOCERT=1 ;   shift 1 ;;
        -l|--nolibs)   NOLIBS=1 ;   shift 1 ;;
        -n|--nosoft)   NOSOFT=1 ;   shift 1 ;;
        -u|--dbuser)   DBUSER=$2;   shift 2 ;;
        -p|--dbpass)   DBPASS=$2;   shift 2 ;;
        -d|--dbname)   DBNAME=$2;   shift 2 ;;
        -s|--dbhost)   DBHOST=$2;   shift 2 ;;
        -h|--help)     print_usage; exit 0  ;;
        --) shift ; break ;;
        *) echo "Skipped unknown parameter: $1" ; shift 1 ;;
    esac
done
}

#################################
# The actual script starts here
#################################

if [ $# == 0 ] ; then print_usage; exit 0; fi

NOCERT=0
NOLIBS=0
NOSOFT=0
DBUSER=SYSDBA
DBPASS=masterkey
DBNAME=abacus
DBHOST=localhost
parse_args "$@"

if [ $NOSOFT == 0 ] ; then install_deps ; fi
if [ $NOLIBS == 0 ] ; then install_libs ; fi
if [ $NOCERT == 0 ] ; then install_cert ; fi
install_abhard "$VERNUMB"
