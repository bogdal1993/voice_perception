FROM postgres:12

COPY *.sql /docker-entrypoint-initdb.d/
COPY ../*.sql /docker-entrypoint-initdb.d/
