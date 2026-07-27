#! /bin/bash

# Shell tests runner.
# Copyright (C) 2017 Red Hat, Inc.
#
# This file is part of resalloc project.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

PREALLOC=1
MAX=4
DBNAME=resalloc-test
: ${DATABASE=sqlite}

. ./testlib

cd "$WORKDIR"

debug "I'm in $PWD"
cleanup_actions=()
cleanup ()
{
    debug "cleanup"
    set +e
    for action in "${cleanup_actions[@]}"
    do
        eval "$action"
    done
}

trap cleanup EXIT

export HOME=$WORKDIR
CLIENT_KEY=$HOME/.config/resalloc-client-key

# The testlib's client() talks plain http, we need https here.
tls_client ()
{
    debug_cmdline "$CLIENT_BIN" --connection https://localhost:"$SERVER_PORT" "$@"
}

mkdir etc .config

info "generate the self-signed certificates"
# The server certificate has to match the hostname the client connects to.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
        -keyout etc/server.key -out etc/server.crt \
        -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost" &>/dev/null
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
        -keyout etc/client.key -out etc/client.crt \
        -subj "/CN=test-client" &>/dev/null
# deliberately not listed in ssl_clients.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
        -keyout etc/unknown.key -out etc/unknown.crt \
        -subj "/CN=unknown-client" &>/dev/null

cat etc/client.crt > etc/clients.pem
cat etc/client.crt etc/client.key > "$CLIENT_KEY"
cp etc/server.crt "$HOME/.config/resalloc-server-cert"

cat > etc/pools.yaml <<EOF
basic:
    max: $MAX
    max_prealloc: $PREALLOC
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    tags:
        - A
EOF

uname=$(id -u -n)
dburl="sqlite:///$WORKDIR/server-sql"
case $DATABASE in
    sqlite) ;;
    postgresql)
        port=${POSTGRESQL_PORT-65432}
        host=/tmp
        datadir=$WORKDIR/pgdata
        info "preparing PostgreSQL server"
        postgresql_start "$port" "$datadir" "$host" &>/dev/null
        createdb -p "$port" -h "$host" "$DBNAME"
        cleanup_actions+=( "pg_ctl stop -D \"$datadir\" -m i >/dev/null" )
        dburl="postgresql://$uname@/$DBNAME?host=$host&port=$port"
        ;;
    *) false ;;
esac

cat > etc/server.yaml <<EOF
db_url: "$dburl"
logdir: $WORKDIR
port: $SERVER_PORT
loglevel: debug
ssl_certfile: $WORKDIR/etc/server.crt
ssl_keyfile: $WORKDIR/etc/server.key
ssl_clients: $WORKDIR/etc/clients.pem
EOF

export CONFIG_DIR=$WORKDIR/etc

server &>/dev/null
cleanup_actions+=( "shutdown_server $server_pid" )

counter=30
while ! maint resource-list &>/dev/null; do
    counter=$(( counter - 1 ))
    test $counter -gt 0
done

wait_num=$PREALLOC
wait_up_resources "preallocated"

info "client with a trusted certificate is allowed"
get_ticket_result=$(tls_client ticket --tag A)
assert "no ticket returned" "test -n \"$get_ticket_result\""
wait_ticket_resolved "$get_ticket_result"

info "client without a certificate is rejected"
mv "$CLIENT_KEY" "$CLIENT_KEY.off"
! tls_client ticket --tag A &>/dev/null \
    || fatal "client without a certificate was allowed"
mv "$CLIENT_KEY.off" "$CLIENT_KEY"

info "client with an untrusted certificate is rejected"
cat etc/unknown.crt etc/unknown.key > "$CLIENT_KEY"
! tls_client ticket --tag A &>/dev/null \
    || fatal "client with an untrusted certificate was allowed"
cat etc/client.crt etc/client.key > "$CLIENT_KEY"

info "plain http against the https server is not served"
! client ticket --tag A &>/dev/null \
    || fatal "plain http request was served"

info "check that the rejected clients took no tickets"
assert_ticket_count 1 "only the first client should have a ticket"

info "the trusted client still works"
get_ticket_result=$(tls_client ticket --tag A)
assert "no ticket returned" "test -n \"$get_ticket_result\""
wait_ticket_resolved "$get_ticket_result"

info "ssl_clients without ssl_certfile warns that TLS is disabled"
# The server keeps running (plain http) in this case, so make sure the log
# says why - and that it doesn't claim TLS was simply never configured.
mkdir bad-etc
cp etc/pools.yaml bad-etc/pools.yaml
badlog=$WORKDIR/badlog
mkdir "$badlog"
cat > bad-etc/server.yaml <<EOF
db_url: "sqlite:///$WORKDIR/server-sql-bad"
logdir: $badlog
port: $(( SERVER_PORT + 100 ))
loglevel: debug
ssl_clients: $WORKDIR/etc/clients.pem
EOF
CONFIG_DIR=$WORKDIR/bad-etc timeout 20 "$SERVER_BIN" &>/dev/null || :
grep -q "ssl_clients is set but ssl_certfile is not" "$badlog/main.log" \
    || fatal "no warning about ssl_clients without ssl_certfile"

# vi: ft=sh
