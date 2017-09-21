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

PREALLOC=5
MAX=15
DBNAME=resalloc-test
: ${DATABASE=sqlite}

. ./testlib

cd "$WORKDIR"

debug "I'm in $PWD"
cleanup_actions=()
cleanup ()
{
    set +e
    for action in "${cleanup_actions[@]}"
    do
        eval "$action"
    done
}

trap cleanup EXIT

mkdir etc
cat > etc/pools.yaml <<EOF
basic:
    max: $MAX
    max_prealloc: $PREALLOC
    cmd_new: "echo \$RESALLOC_NAME"
    cmd_delete: "true"
    tags:
        - A
        - B
EOF

uname=$(id -u -n)
dburl="sqlite:///$WORKDIR/server-sql"
case $DATABASE in
    sqlite) ;;
    postgresql)
        port=${POSTGRESQL_PORT-5432}
        dburl="postgresql://$uname@/$DBNAME?host=/tmp&port=$port"
        createdb -p $port -h /tmp "$DBNAME"
        cleanup_actions+=( "dropdb -p $port -h /tmp $DBNAME" )
        port=${POSTGRESQL_PORT-5432}
        ;;
    *) false ;;
esac

cat > etc/server.yaml <<EOF
db_url: "$dburl"
main_logfile: $WORKDIR/main-log
port: $SERVER_PORT
loglevel: debug
EOF

export CONFIG_DIR=$WORKDIR/etc

server &>/dev/null
cleanup_actions+=( "kill $server_pid" )

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

info "check that after some time still only $PREALLOC are available"
sleep 3
up=$(maint resource-list --up | wc -l)
test "$up" = "$PREALLOC"

info "take all the resources which should be available"
set -- "A B" A "A B" B "B A"
for _ in $(seq 1 $PREALLOC); do
    tags=$1 ; shift || :
    test -n "$tags" || tags=B
    cmd=(client ticket)
    for tag in $tags; do
        cmd+=(--tag $tag)
    done
    "${cmd[@]}" >/dev/null
done
sleep 1
for id in $(seq 1 $PREALLOC); do
    client ticket-check "$id" >/dev/null
done

info "take some more tickets, to reach the maximum"
for id in $(seq $(( PREALLOC + 1 )) $MAX); do
    client ticket --tag A >/dev/null
done
sleep 2
for id in $(seq $(( PREALLOC + 1 )) $MAX); do
    client ticket-check $id >/dev/null
done


info "take one more, which should wait"
id=$(client ticket --tag A)
client ticket-wait "$id" &>/dev/null &
waiting_pid=$!
sleep 3
# EXIT_STATUS if something is killed
kill $waiting_pid

# this should fail
! client ticket-check "$id" &>/dev/null

info "release one ticket and check that the waiting ticket now succeeds"
client ticket-close 1 &>/dev/null
sleep 2
client ticket-wait "$id" &>/dev/null  &
waiting_pid=$!
sleep 1
! kill $waiting_pid &>/dev/null
client ticket-check "$id" >/dev/null

info "close all the tickets now and check that again $PREALLOC is up"
for i in $(seq 2 $(( MAX + 1 ))); do
    client ticket-close "$i"
done
sleep 2

up=$(maint resource-list --up | wc -l)
test "$up" -eq "$PREALLOC"

# vi: ft=sh
