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

NORMAL_MAX=5
NORMAL_PREALLOC=3
TIME_MAX=4
TIME_PREALLOC=2
COUNT_MAX=2
COUNT_PREALLOC=1

MAX=$(( NORMAL_MAX + COUNT_MAX + TIME_MAX ))
PREALLOC=$(( NORMAL_PREALLOC + COUNT_PREALLOC + TIME_PREALLOC ))

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
reuse:
    max: $NORMAL_MAX
    max_prealloc: $NORMAL_PREALLOC
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    cmd_release: "echo >&2 stderr; echo stdout; echo \$RESALLOC_RESOURCE_DATA | base64 --decode"
    livecheck_period: 1
    tags:
        - A
    reuse_opportunity_time: 60
    reuse_max_count: 3
    reuse_max_time: 60

reuse_count:
    max: $COUNT_MAX
    max_prealloc: $COUNT_PREALLOC
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    livecheck_period: 1
    tags:
        - B
    reuse_opportunity_time: 60
    reuse_max_count: 1
    reuse_max_time: 60

reuse_time:
    max: $TIME_MAX
    max_prealloc: $TIME_PREALLOC
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    livecheck_period: 1
    tags:
        - C
    reuse_opportunity_time: 60
    reuse_max_count: 0
    reuse_max_time: 15
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
    test $counter -gt 0 || fail "some resource did not start"
    sleep 1
done

info "check that after some time still only $PREALLOC are available"
sleep 3
up=$(maint resource-list --up | wc -l)
test "$up" = "$PREALLOC"


info '1. case: take -> return -> re-take'
id=$(client ticket --tag A --sandbox=sb)
client ticket-wait "$id" > "$WORKDIR/first-ticket"
client ticket-close "$id"
sleep 2
id=$(client ticket --tag A --sandbox=sb)
client ticket-wait "$id" > "$WORKDIR/second-ticket"
resource_id=$(maint resource-list | grep "ticket=$id" | cut -d' ' -f 1)
test -n "$resource_id" || fail "no assigned resource??"
set -- "$WORKDIR/hooks/"*000"${resource_id}_release"
release_log=$1
test 1 -eq "$(grep -c stdout "$release_log")" || fail "no stdout in release log"
test 1 -eq "$(grep -c stderr "$release_log")" || fail "no stderr in release log"
test 1 -eq "$(grep -c RESALLOC_NAME= "$release_log")" || fail "no data decoded"
client ticket-close "$id"
diff "$WORKDIR/first-ticket" "$WORKDIR/second-ticket" || fail "different output"


info '2. case: take all -> take one more -> release one'
ids=()
first_id=$(client ticket --tag A --sandbox=first-sb)
for _ in `seq $(( NORMAL_MAX - 1 ))`; do
    id="$(client ticket --tag A --sandbox=second-sb)"
    ids+=( "$id" )
done
id=$(client ticket --tag A --sandbox=first-sb)
client ticket-wait "$id" &>/dev/null &
waiting_pid=$!
sleep 3
kill -0 "$waiting_pid" || fail "doesn't wait"
client ticket-close "$first_id"
sleep 1
! kill -0 "$waiting_pid" &>/dev/null || fail "exists"
client ticket-wait "$first_id" > "$WORKDIR/first"
client ticket-wait "$id" > "$WORKDIR/second"
diff "$WORKDIR/first" "$WORKDIR/second"
ids+=( "$id" )
for id in "${ids[@]}"; do
    client ticket-close "$id"
done
test "$(maint ticket-list | wc -l)" -eq 0


info '3. case: count limit'
for attempt in `seq 3`; do
    ticket=$(client ticket --tag B --sandbox=sb)
    client ticket-wait "$ticket" >/dev/null
    client ticket-close "$ticket"
    eval "id_$attempt=$ticket"
    sleep 1
done

client ticket-wait "$id_1" > id1
client ticket-wait "$id_2" > id2
client ticket-wait "$id_3" > id3
diff id1 id2 >/dev/null
! diff id2 id3 >/dev/null || fail "reused"


info '4. case: time limit'
ticket_1=$(client ticket --tag C --sandbox=sb)
client ticket-wait "$ticket_1" >/dev/null
client ticket-close "$ticket_1"
close_time=$SECONDS
while true; do
    released=$(maint resource-list --up | grep releases=1 | grep reuse_time | wc -l)
    if test $released -ge 1; then
        break
    fi
    sleep 0.1
    test $(( SECONDS - close_time )) -gt 5 && fail "timeout"
done

ticket_2=$(client ticket --tag C --sandbox=sb)
client ticket-wait "$ticket_2" >/dev/null
client ticket-close "$ticket_2"
sleep 15  # reach the time limit
ticket_3=$(client ticket --tag C --sandbox=sb)
client ticket-wait "$ticket_3" >/dev/null
client ticket-close "$ticket_3"

client ticket-wait "$ticket_1" > id1
client ticket-wait "$ticket_2" > id2
client ticket-wait "$ticket_3" > id3

diff id1 id2
! diff id2 id3 >/dev/null || fail "reused"

# vi: ft=sh
