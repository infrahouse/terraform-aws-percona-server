"""
ASG Lifecycle Hook handler for Orchestrator Raft peer management.

Triggered by EventBridge when ASG launches or terminates an instance.
Adds/removes the instance from the Raft peer list so Orchestrator
maintains a consistent cluster membership.
"""

import json
import logging
import os

import boto3
from infrahouse_core.orchestrator.exceptions import IHRaftLeaderNotFound, IHRaftPeerError
from infrahouse_core.orchestrator.raft_cluster import OrchestratorRaftCluster
from infrahouse_core.orchestrator.raft_node import OrchestratorRaftNode

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

REGION = os.environ.get("REGION")
ASG_NAME = os.environ.get("ASG_NAME")


def lambda_handler(event, context):
    """Handle ASG lifecycle events for Raft peer management.

    :param event: EventBridge event with ASG lifecycle detail.
    :param context: Lambda context (unused).
    :return: Dict with statusCode and result message.
    """
    LOG.info("Received event: %s", json.dumps(event))

    detail = event["detail"]
    instance_id = detail["EC2InstanceId"]
    transition = detail["LifecycleTransition"]
    hook_name = detail["LifecycleHookName"]
    asg_name = detail["AutoScalingGroupName"]

    LOG.info(
        "Lifecycle event: transition=%s instance=%s hook=%s asg=%s",
        transition,
        instance_id,
        hook_name,
        asg_name,
    )

    autoscaling = boto3.client("autoscaling", region_name=REGION)

    if transition == "autoscaling:EC2_INSTANCE_LAUNCHING":
        # Launch hook is completed by the instance itself (raft-join.sh
        # in post_runcmd) after Puppet bootstraps Orchestrator.
        _handle_launch(instance_id)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "instance_id": instance_id,
                "transition": transition,
                "result": "DEFERRED",
            }),
        }

    if transition == "autoscaling:EC2_INSTANCE_TERMINATING":
        try:
            cluster = OrchestratorRaftCluster(asg_name=asg_name, region=REGION)
            _handle_terminate(cluster, instance_id)
        except IHRaftLeaderNotFound:
            LOG.warning(
                "No Raft leader found — cannot remove peer %s, reconcile will clean up",
                instance_id,
            )
        except IHRaftPeerError as exc:
            LOG.warning("Raft peer error removing %s: %s", instance_id, exc)
    else:
        LOG.warning("Unknown transition: %s", transition)

    lifecycle_result = "CONTINUE"

    LOG.info(
        "Completing lifecycle action: hook=%s result=%s",
        hook_name,
        lifecycle_result,
    )
    autoscaling.complete_lifecycle_action(
        LifecycleHookName=hook_name,
        AutoScalingGroupName=asg_name,
        InstanceId=instance_id,
        LifecycleActionResult=lifecycle_result,
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "instance_id": instance_id,
                "transition": transition,
                "result": lifecycle_result,
            }
        ),
    }


def _handle_launch(
    instance_id: str,
) -> None:
    """Log a launching instance — peer addition happens after bootstrap.

    The instance is in Pending:Wait at this point: no SSM agent, no
    Orchestrator.  Trying to add it as a Raft peer now would hang
    (the leader's add-peer API tries to contact the new node).
    Instead we just CONTINUE and let the instance bootstrap.  Puppet
    configures Orchestrator with RaftNodes containing all peers, so
    the new instance joins the Raft cluster on its own once it starts.

    :param instance_id: EC2 instance ID of the new instance.
    """
    LOG.info(
        "Instance %s is launching — peer will join Raft after bootstrap",
        instance_id,
    )


def _handle_terminate(
    cluster: OrchestratorRaftCluster,
    instance_id: str,
) -> None:
    """Remove stale Raft peers that are no longer in the ASG.

    We cannot look up the terminating instance's hostname/IP — it may
    already be shutting down.  Instead, compare the leader's raft-peers
    list against live ASG instances and remove any peer that doesn't
    belong.  Best-effort: timeouts are logged and left for the
    scheduled reconcile Lambda.

    :param cluster: OrchestratorRaftCluster instance.
    :param instance_id: EC2 instance ID being terminated (for logging).
    """
    leader = cluster.leader
    LOG.info(
        "Terminate event for %s — checking for stale Raft peers via leader %s (%s)",
        instance_id,
        leader.instance.instance_id,
        leader.peer_addr,
    )

    # Build a set of IPs and hostnames for all live ASG instances
    live_hosts = set()
    for node in cluster.nodes:
        live_hosts.add(node.hostname)
        if node.private_ip is not None:
            live_hosts.add(node.private_ip)

    # Find Raft peers not matching any live instance
    for addr in leader.raft_peers:
        host = addr.split(":")[0]
        if host not in live_hosts:
            stale_peer = OrchestratorRaftNode.from_peer_addr(addr)
            LOG.info("Removing stale Raft peer %s", addr)
            try:
                leader.remove_peer(stale_peer)
                LOG.info("Removed stale peer %s", addr)
            except TimeoutError:
                LOG.warning(
                    "Timed out removing peer %s — reconcile will clean up",
                    addr,
                )
