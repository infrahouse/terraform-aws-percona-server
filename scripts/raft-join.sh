#!/usr/bin/env bash
# Join the Orchestrator Raft cluster after Puppet bootstrap.
#
# Waits for local Orchestrator to be healthy, then discovers the Raft
# leader by querying known peers (from local raft-status).  Asks the
# leader to add this node.  On a fresh cluster (no leader yet), all
# nodes bootstrap together and elect a leader — skip the add-peer
# step.  After joining, cleans up stale Raft peers that don't match
# live ASG instances.  Finally, complete the ASG lifecycle hook so
# the instance transitions to InService.

set -euo pipefail

ORCHESTRATOR_PORT=3000
HEALTH_URL="http://localhost:${ORCHESTRATOR_PORT}/api/health"

echo "Waiting for local Orchestrator to become healthy..."
while ! curl -sf "${HEALTH_URL}" > /dev/null 2>&1; do
    sleep 5
done
echo "Orchestrator is healthy."

MY_ADDR=$(curl -sf "http://localhost:${ORCHESTRATOR_PORT}/api/raft-status" | jq -r .RaftAdvertise)
echo "Local Raft address: ${MY_ADDR}"

# Get the list of known peers from local Orchestrator config.
# We can't ask ourselves for the leader — we're not in the quorum yet.
# Instead, ask each peer until one tells us who the leader is.
PEERS=$(curl -sf "http://localhost:${ORCHESTRATOR_PORT}/api/raft-status" | jq -r '.Peers[]')

LEADER=""
for PEER in ${PEERS}; do
    PEER_IP="${PEER%%:*}"
    # Skip ourselves
    if [ "${PEER}" = "${MY_ADDR}" ]; then
        continue
    fi
    echo "Asking peer ${PEER_IP} for the Raft leader..."
    LEADER=$(curl -sf "http://${PEER_IP}:${ORCHESTRATOR_PORT}/api/raft-leader" | jq -r '.' || true)
    if [ -n "${LEADER}" ] && [ "${LEADER}" != "" ]; then
        echo "Peer ${PEER_IP} reports leader: ${LEADER}"
        break
    fi
done

if [ -n "${LEADER}" ]; then
    LEADER_IP="${LEADER%%:*}"
    echo "Adding ourselves to Raft via leader ${LEADER_IP}..."
    curl -sf "http://${LEADER_IP}:${ORCHESTRATOR_PORT}/api/raft-add-peer/${MY_ADDR}" || true
    echo "Add-peer request sent."
else
    echo "No Raft leader found — fresh cluster, skipping add-peer."
fi

# --- Clean up stale Raft peers ---
# The Raft log/snapshot accumulates peer addresses from dead instances.
# Compare the leader's peer list against live ASG instance IPs and
# remove any peer that doesn't belong.

cleanup_stale_peers() {
    if [ -z "${LEADER}" ]; then
        echo "No leader known — skipping stale peer cleanup."
        return
    fi

    LEADER_IP="${LEADER%%:*}"

    # Get cluster_id from Puppet custom facts.
    CLUSTER_ID=$(jq -r '.percona.cluster_id' /etc/puppetlabs/facter/facts.d/custom.json)

    if [ -z "${CLUSTER_ID}" ] || [ "${CLUSTER_ID}" = "null" ]; then
        echo "Could not determine cluster_id — skipping stale peer cleanup."
        return
    fi
    echo "Cluster ID: ${CLUSTER_ID}"

    # Get private IPs of all live instances in this cluster.
    # ih-ec2 list -c returns comma-separated IPs (empty for terminated).
    LIVE_IPS=$(ih-ec2 list --cluster_id="${CLUSTER_ID}" -c \
        | tr ',' '\n' | grep -v '^$')

    echo "Live instance IPs: ${LIVE_IPS}"

    # Get the leader's current Raft peer list.
    RAFT_PEERS=$(curl -sf \
        "http://${LEADER_IP}:${ORCHESTRATOR_PORT}/api/raft-status" \
        | jq -r '.Peers[]') || true

    if [ -z "${RAFT_PEERS}" ]; then
        echo "Could not get leader's Raft peers — skipping cleanup."
        return
    fi

    for PEER_ADDR in ${RAFT_PEERS}; do
        PEER_HOST="${PEER_ADDR%%:*}"
        # Check if this peer's IP is among live ASG instances.
        if ! echo "${LIVE_IPS}" | grep -qw "${PEER_HOST}"; then
            echo "Removing stale Raft peer ${PEER_ADDR}..."
            curl -sf \
                "http://${LEADER_IP}:${ORCHESTRATOR_PORT}/api/raft-remove-peer/${PEER_ADDR}" \
                || true
            echo "Removed ${PEER_ADDR}."
        fi
    done

    echo "Stale peer cleanup complete."
}

cleanup_stale_peers

echo "Completing ASG lifecycle hook..."
ih-aws autoscaling complete raft-launch
echo "Done."
