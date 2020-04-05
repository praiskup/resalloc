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
    debug "cleanup"
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
    cmd_new: "echo >&2 before; env | grep RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
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

info "check that after some time still only $PREALLOC are available"
sleep 3
up=$(maint resource-list --up | wc -l)
test "$up" = "$PREALLOC"

# No tickets yet!
test $(maint ticket-list | wc -l) -eq 0

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

test $(maint ticket-list | wc -l) -eq $PREALLOC

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
client ticket-wait "$id" &>/dev/null  &
waiting_pid=$!
sleep 5
! kill $waiting_pid &>/dev/null

alloc_output=$(client ticket-wait "$id")
while read -r line; do
    case $line in
        before|after) ;;
        RESALLOC_ID=*) ;;
        RESALLOC_NAME=basic_*) ;;
        RESALLOC_POOL_ID=basic) ;;
        RESALLOC_ID_IN_POOL=*) ;;
        *) fail "invalid data in output: $line"
    esac
done <<<"$alloc_output"
lines=$(echo "$alloc_output" | grep ^RESALLOC | wc -l)
test $lines -eq 4 || fail "invalid RESALLOC_ variables"

client ticket-check "$id" >/dev/null

info "close all the tickets now and check that again $PREALLOC is up"
for i in $(seq 2 $(( MAX + 1 ))); do
    client ticket-close "$i" || error "can't close ticket"
done

success=false
for _ in $(seq 30); do
    up=$(maint resource-list | wc -l)
    test "$up" -eq "$PREALLOC" && success=true && break
    sleep 1
done
$success || die "unexpected number of resources after 30s: $up"
test $(maint resource-list --up | wc -l) -eq "$PREALLOC"

check_id=$(printf "%06d" 1)
info "check that all the log files are in place"
test -f "$WORKDIR"/hooks/"$check_id"_alloc
test -f "$WORKDIR"/hooks/"$check_id"_terminate
test -f "$WORKDIR"/hooks/"$check_id"_watch

info "check that log files contain both stderr and stdout"
grep -q before "$WORKDIR"/hooks/"$check_id"_alloc
grep -q after  "$WORKDIR"/hooks/"$check_id"_alloc
grep -q stdout "$WORKDIR"/hooks/"$check_id"_terminate
grep -q stderr "$WORKDIR"/hooks/"$check_id"_terminate
grep -q stdout "$WORKDIR"/hooks/"$check_id"_watch
grep -q stderr "$WORKDIR"/hooks/"$check_id"_watch

info "test force-delete of two resources"
maint resource-delete 20 21
# hack: enforce manager's loop
client ticket --tag A >/dev/null

info "check that multiple checks are logged into single log file"
sleep 21 # there's 10s interval in Watcher.loop()
test "2" -le "$(grep stderr "$WORKDIR"/hooks/000017_watch | wc -l)"
test "2" -le "$(grep stdout "$WORKDIR"/hooks/000017_watch | wc -l)"

list=$(maint resource-list)
test $(echo "$list" | wc -l) -eq $(( PREALLOC + 1 ))

for i in 20 21; do
    echo "$list" | grep "^$i" && fail "id $i shouldn't exist anymore"
done

info "check that RESALLOC_ID_IN_POOL has sane numbers"
number_of_tickets=40
tickets=
for n in `seq $number_of_tickets`; do
    tickets+=' '$(client ticket --tag A)
done

while true; do
    tickets=$(maint ticket-list)
    test -z "$tickets" && break # processed
    while read -r line; do
        case $line in
        *resource=*)
            # has resource already
            eval 'set -- $line'
            ticket=$1
            output=$(client ticket-check "$ticket")
            while read -r output_line; do
                case $output_line in
                RESALLOC_ID_IN_POOL=*)
                    old_IFS=$IFS
                    IFS='='
                    eval 'set -- $output_line'
                    IFS=$old_IFS
                    test "$2" -le "$MAX" || fail "unexpected RESALLOC_ID_IN_POOL value $2"
                    ;;
                esac
            done <<<"$output"
            client ticket-close "$ticket"
            ;;
        esac
    done <<<"$tickets"
done

# vi: ft=sh
