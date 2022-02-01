#!/bin/bash

print_usage()
{
  echo -e "
This script deploys Abhard software and accepts the following parameters:

-c, --cert - also deploy certificates
-l, --libs - also deploy service libraries
-v, --version - version of the abhard to deploy
-d, --directory - destination directory on the remote host
-r, --remote - remote host for the deployment
-h, --help or without params - print this text

Examples:

$0 --version=1.0 --nocert -l
    Deploy Abhard version 1.0, to the default location without certificates and libraries

$0 --version=latest
    Deploy the latest available Abhard and all the necessities

Possible version values: stable, latest    
"
}


# Deploy crypto libs
deploy_libs()
{
  echo "Encryption libraries deployment is not implemented yet"
}

# Deploy certificates
deploy_cert()
{
  echo "Deploy certificates"
  archive=cert.zip
  zip $archive cert/*
  scp $archive $TGTHOST:$REMTDIR
  rm -f $archive
}

# Deploy abhard
deploy_abhard()
{
  echo "Deploy abhard version $1"
  archive=abhard-$1.zip
  zip $archive src/* -x src/__pycache__/ -x src/EUSignCP.py -x src/_EUSignCP.so
  scp $archive $TGTHOST:$REMTDIR
  rm -f $archive
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
        -d|--directory)REMTDIR=$2 ; shift 2 ;;
        -r|--remote)   TGTHOST=$2 ; shift 2 ;;
        -c|--cert)     DOCERT=1 ;   shift 1 ;;
        -l|--libs)     DOLIBS=1 ;   shift 1 ;;
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

DOCERT=0
DOLIBS=0
TGTHOST=abacus.in.ua
REMTDIR=/var/www/abacus.in.ua/files/abhard/
parse_args "$@"

CURNTDIR=`pwd`
SCRPTDIR=`dirname $(readlink -f $0)`
ABHRDDIR=`dirname $SCRPTDIR`
cd $ABHRDDIR

if [ $DOLIBS == 1 ] ; then deploy_libs ; fi
if [ $DOCERT == 1 ] ; then deploy_cert ; fi
deploy_abhard "$VERNUMB"

cd $CURNTDIR