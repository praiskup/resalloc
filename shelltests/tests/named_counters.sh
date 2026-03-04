NORMAL_MAX=5
NORMAL_PREALLOC=3
TIME_MAX=4
TIME_PREALLOC=2
COUNT_MAX=2
COUNT_PREALLOC=1

MAX=$(( NORMAL_MAX + COUNT_MAX + TIME_MAX ))

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
first:
    max: 4
    max_prealloc: 1
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    cmd_release: "echo >&2 stderr; echo stdout; echo \$RESALLOC_RESOURCE_DATA | base64 --decode"
    livecheck_period: 1
    tags:
        - A
    reuse_max_count: 3
    # Keep this one running!
    reuse_max_time: 60
    named_counters:
        - counter_1
second:
    max: 4
    max_prealloc: 1
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    cmd_release: "echo >&2 stderr; echo stdout; echo \$RESALLOC_RESOURCE_DATA | base64 --decode"
    livecheck_period: 1
    tags:
        - B
    named_counters:
        - counter_1
        - counter_2
third:
    max: 4
    max_prealloc: 1
    cmd_new: "echo >&2 before; env | grep ^RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    cmd_livecheck: "echo >&2 stderr; echo stdout"
    cmd_release: "echo >&2 stderr; echo stdout; echo \$RESALLOC_RESOURCE_DATA | base64 --decode"
    livecheck_period: 1
    tags:
        - C
    named_counters:
        - counter_1
        - counter_2
        - counter_3
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

PREALLOC=3
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
        error "too many resources"
    }
    test $counter -gt 0 || fail "some resource did not start"
    sleep 1
done
id1=$(client ticket --tag A)
id2=$(client ticket --tag B)
id3=$(client ticket --tag C)

set -e

info "Wait three tickets."
client ticket-wait "$id1" > ticket1
client ticket-wait "$id2" > ticket2
client ticket-wait "$id3" > ticket3

info "Search for expected counter values."
grep RESALLOC_NAMED_COUNTER_counter_1=0 ticket1 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_2=0 ticket2 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_1=1 ticket2 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_3=0 ticket3 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_2=1 ticket3 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_1=2 ticket3 >/dev/null

info "Close tickets, wipe existing workers, and take one more ticket."
client ticket-close "$id1"
client ticket-close "$id2"
client ticket-close "$id3"

sleep 3
# recyclate resources 4, 5 and 6
maint resource-delete --all
sleep 3

id4=$(client ticket --tag C)
client ticket-wait "$id4" > ticket4

info "Check for the right counters"
grep RESALLOC_NAMED_COUNTER_counter_3=0 ticket4 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_2=1 ticket4 >/dev/null
grep RESALLOC_NAMED_COUNTER_counter_1=2 ticket4 >/dev/null
