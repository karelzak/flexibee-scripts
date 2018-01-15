#!/bin/bash

HESLO="$1"
SOUBOR="$2"
FIRMA="$3"
DOMAIN="$4"

if [ -z $HESLO ] || [ -z $SOUBOR ]; then
	echo "$0 <heslo> <soubor> <firma> <domain>"
	exit 1
fi

curl -u ${HESLO} -k -L https://${DOMAIN}.flexibee.eu:5434/c/${FIRMA}/faktura-vydana.xml -T ${SOUBOR}"
