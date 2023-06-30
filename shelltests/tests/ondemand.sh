#! /bin/bash

# Check that "on demand" resources work correctly in Resalloc
# Copyright (C) 2023 Red Hat, Inc.
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

DBNAME=resalloc-test-on-demand
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

mkdir etc
cat > etc/pools.yaml <<EOF
---
basic:
    max: 2
    max_prealloc: 1
    cmd_new: "echo >&2 before; env | grep RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    tags:
        - A
        - B
        - prealloc

ondemand1:
    max: 3
    max_prealloc: 5  # unused
    cmd_new: "echo >&2 before; sleep 3 ; env | grep RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    tags:
        - A
        - B
        - C1
        - name: priority  # This tag is prioritized here in ondemand1
          priority: 2
    tags_on_demand:
        - ondemand  # This tag is prioritized in ondemand2 pool
        - ondemand1
        - ondemand_not_prioritized
    reuse_opportunity_time: 5

ondemand2:
    max: 3
    max_prealloc: 5  # unused
    cmd_new: "echo >&2 before; sleep 3 ; env | grep RESALLOC_; echo >&2 after"
    cmd_delete: "echo >&2 stderr; echo stdout"
    tags:
        - A
        - B
        - C2
        - name: priority
          priority: 1
    tags_on_demand:
        - name: ondemand
          priority: 1
        - ondemand2
        - ondemand_not_prioritized
    reuse_opportunity_time: 5
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

# Wait for the DB startup and init.
counter=30
while ! maint resource-list &>/dev/null; do
    counter=$(( counter - 1 ))
    test $counter -gt 0
done

# this ticket is never going to be closed, never matches any pool, and never
# creates any demand resource
get_ticket --tag A --tag B --tag C

# this ticket matches ondemand2, though it doesn't start a new resource
get_ticket --tag A --tag B --tag C2

# This ticket takes one pre-alloc resource, 2nd one gets preallocated
get_ticket --tag A --tag B --tag prealloc
ticket_in_basic_prealloc=$get_ticket_result

# This ticket triggers one on-demand resource startup
get_ticket --tag A --tag B --tag ondemand

wait_num=3 wait_up_resources "2x 'basic', 1x 'ondemand'"

# Two assigned resources, one on-demand, one preallocated
assert_assigned_ticket_count 2 "First check"

# These tickets match all pools, but only prealloc are taken.
# First is assigned, second one stays unresolved till a very late state of this
# test script
get_ticket --tag A --tag B
get_ticket --tag A --tag B
remember_ticket_for_later=$get_ticket_result
get_ticket --tag A --tag B
remember_ticket_for_later2=$get_ticket_result
sleep 3

# Three assigned resources, one on-demand, two preallocated
assert_assigned_ticket_count 3 "Second check"

wait_num=3 wait_up_resources "2x 'basic', 1x 'ondemand' (nothing changed)"

assert_ticket_count 7 "check before harder tasks"
assert_resource_count 3 "check before harder tasks"

# "ondemand" tag itself prioritizes ondemand2 pool
get_ticket --tag A --tag B --tag ondemand --sandbox=take_one
on_demand_ticket1=$get_ticket_result
# .. but with "priority" tag it flips back to ondemand1
get_ticket --tag A --tag B --tag ondemand --tag priority --sandbox=take_two
on_demand_ticket2=$get_ticket_result

wait_ticket_resolved "$on_demand_ticket1" "in ondemand2"
on_demand_resource1=$wait_ticket_resolved_result_resource
wait_ticket_resolved "$on_demand_ticket2" "in ondemand1"
on_demand_resource2=$wait_ticket_resolved_result_resource

# Priorities are respected while allocating resources!
assert_starts_with "$on_demand_resource1" "ondemand2_" "Checking ondemand2 pool is assigned"
assert_starts_with "$on_demand_resource2" "ondemand1_" "Checking ondemand1 pool is assigned"

wait_num=5 wait_up_resources "two more on-demand machines"

# Check that first-defined pool (ondemand1) is chosen first over the latter
# (determinism test)
get_ticket --tag A --tag B --tag ondemand_not_prioritized
wait_ticket_resolved "$get_ticket_result" "on demand, but not prioritized"
assert_starts_with "$wait_ticket_resolved_result_resource" "ondemand1_" \
    "Not prioritized ticket should get the first defined pool"

# This one starts the last have Check that first-defined pool is chosen first over the latter (determinism)
get_ticket --tag A --tag B --tag ondemand2 --sandbox=retake
last_resolved_ticket=$get_ticket_result
# This two ticket are going to wait till the NEXT one is resolved because it is not
# using on-demand tag.  The C2 ticket explicitly selects ondemand2 pool, the
# next ticket can be handled by any pool actually, but all the other resources
# are allocated in 'basic' to take care of.
get_ticket --tag A --tag B --tag C2 --sandbox=retake
unresolved_ticket_not_on_demand=$get_ticket_result
get_ticket --tag A --tag B          --sandbox=retake
unresolved_ticket_not_on_demand_basic=$get_ticket_result
# This ticket is going to wait till the $last_resolved_ticket is closed,
# blocking the previous because we reached the "max" limit (so we are not
# starting new resources)
get_ticket --tag A --tag B --tag ondemand2 --sandbox=retake
unresolved_ticket=$get_ticket_result

wait_ticket_resolved "$last_resolved_ticket" "the last one allocated"
last_resource=$wait_ticket_resolved_result_resource
assert_starts_with "$last_resource" "ondemand2_" "explicit ondemand2"
assert_resource_count 7 "check before harder tasks"

# Try re-taking of on-demand resources by on-demand task that was waiting on the
# "max" limit.  There are other two tickets that we could take by this resource,
# but on-demand ticket has more priority.
client ticket-close "$last_resolved_ticket"
wait_ticket_resolved "$unresolved_ticket" "taking a waiting on demand task"

# Try re-taking of on-demand resources even by non-on-demand task
client ticket-close "$unresolved_ticket"
wait_ticket_resolved "$unresolved_ticket_not_on_demand" "taking non-on-demand task"

# Try re-taking of on-demand resources by non-on-demand task that can be handled
# by non-on-demand pool, too (while the basic pool is full).
client ticket-close "$unresolved_ticket_not_on_demand"
wait_ticket_resolved "$unresolved_ticket_not_on_demand_basic" "taking also task for basic pool"

# We still get the same resource ID!
assert "check retaken resource" "test $last_resource = $wait_ticket_resolved_result_resource"
assert_resource_count 7 "final check before harder tasks"

# This triggers a resource startup in ondemand1 pool (ondemand2 is full).  We
# give-up, the resource is started anyway and it takes the old unresolved
# ticket $remember_ticket_for_later
get_ticket --tag A --tag B --tag ondemand
sleep 2
client ticket-close "$get_ticket_result"

wait_ticket_resolved "$remember_ticket_for_later" "additional ondemand resource taking old basic ticket"
assert_starts_with "$wait_ticket_resolved_result_resource" "ondemand1_" \
    "Checking ondemand1 pool is assigned to $remember_ticket_for_later"

# Close a very old ticket, which deallocates resource in 'basic', new one is
# started and it finally takes '$remember_ticket_for_later2'
client ticket-close "$ticket_in_basic_prealloc"

wait_ticket_resolved "$remember_ticket_for_later2" "take ticket by basic pool again"
assert_starts_with "$wait_ticket_resolved_result_resource" "basic_"

# Drop remaining tickets, deallocate resources (one 'basic' preallocated
# remains).
for i in  1 2 4 5 6 7 8 9 10 13; do
    client ticket-close $i
done
assert_ticket_count 0 "all should be deallocated,"

# These two tickets are allocated to a and new basic resources
get_ticket --tag A --tag B
check=$get_ticket_result
get_ticket --tag A --tag B
wait_ticket_resolved "$get_ticket_result" "fresh new basic resource #1"
assert_starts_with "$wait_ticket_resolved_result_resource" "basic_"
wait_ticket_resolved "$check" "fresh new basic resource #2"
assert_starts_with "$wait_ticket_resolved_result_resource" "basic_"
sleep 7  # waste the reuse_opportunity_time
assert_resource_count 2 "only two basic resources again"

# vi: ft=sh
