#!/bin/bash
# Cree la base de preproduction a cote de celle de production.
#
# PostgreSQL n'execute ce script qu'au TOUT PREMIER demarrage, quand le volume
# est vide. Le modifier ensuite n'a aucun effet : il faut supprimer le volume,
# ou creer la base a la main.

set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
	CREATE DATABASE meglabs_staging;
	GRANT ALL PRIVILEGES ON DATABASE meglabs_staging TO $POSTGRES_USER;
EOSQL
