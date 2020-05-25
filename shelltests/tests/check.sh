#! /bin/bash

# Shell tests runner.
# Copyright (C) 2020 Red Hat, Inc.
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

PREALLOC=5
MAX=15
DBNAME=resalloc-test
: "${DATABASE=sqlite}"

. ./testlib

cd "$WORKDIR" || exit 1

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

check_cmd="\
 echo decoded.. ; \
 echo \"\$RESALLOC_RESOURCE_DATA\" | base64 --decode ; \
 echo not_decoded..; \
 /usr/bin/env | grep ^RESALLOC_RESOURCE_DATA; \
 exit 1"

mkdir etc
cat > etc/pools.yaml <<EOF
basic:
    max: $MAX
    max_prealloc: $PREALLOC
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: '$check_cmd'
    livecheck_period: 1
    tags:
        - A
        - B
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
sleeptime: 1
EOF

export CONFIG_DIR=$WORKDIR/etc

server &>/dev/null
cleanup_actions+=( "shutdown_server $server_pid" )

# Wait for the server to start up.
counter=30
while ! maint resource-list &>/dev/null; do
    counter=$(( counter - 1 ))
    test $counter -gt 0
done

info "Wait for $PREALLOC preallocated machines"
counter=30
while true; do
    up=$(maint resource-list --up | wc -l)
    counter=$(( counter - 1))
    if test "$up" -eq "$PREALLOC"; then
        break
    fi
    test "$up" -lt "$PREALLOC" || {
        maint resource-list --up
        error "too much resources"
    }
    test $counter -gt 0
    sleep 1
done

info "wait till the first set of VMs is deleted by watcher"
while ! test -f "$WORKDIR/hooks/"*006_watch; do
    sleep 1
done

output=$(sort "$WORKDIR/hooks/"*005_watch | uniq)
case $output in
    *RESALLOC_ID=5*) ;;
    *) fail "missing RESALLOC_ID in $output" ;;
esac

# vi: ft=sh
