# Reorganize Project Board: Add Scenario-Based Issues

## Context

The project board (infrahouse/projects/7) is organized by features/components
(Epics: Infrastructure, Puppet Integration, Orchestrator, Backups, Binlog Archival).
This tracks implementation work well, but doesn't capture what the user cares about:
"does my cluster survive failures?"

Now that the core cluster works (bootstrap, replication, Orchestrator), we need
scenario issues that define "done" in terms of user outcomes. Each scenario maps
to an integration test in `test_module.py`.

## Current State (What Works Today)

- Fresh cluster deploy: 3 instances, master election, GTID replication
- NLB write (3306) and read (3307) endpoints
- Orchestrator with Raft consensus, running on all nodes
- Post-failover hooks (NLB re-registration, scale-in protection, DynamoDB, EC2 tags)
- Percona 8.0 and 8.4 version selection
- End-to-end Sakila test (deploy → puppet → create user → load data → query via NLB)
- MySQL credentials in Secrets Manager (root, replication, backup, monitor, orchestrator)
- S3 bucket with lifecycle policies (ready for backups, not yet used)
- DynamoDB with TTL locks (master election, backup/binlog leader slots reserved)

## What's NOT Yet Implemented

- XtraBackup (installation, scheduling, S3 upload)
- Binlog archival to S3
- Backup-based replica bootstrap (new replica restores from S3 instead of live stream)
- Monitoring (CloudWatch, PMM)
- ASG lifecycle hooks

## Proposed Scenarios

### [Scenario] S1: Fresh Cluster Deploy
**Already implemented.** Deploy 3 instances from scratch. Master elected, replicas
join via GTID replication. Write and read NLB endpoints serve traffic.
Test: existing Sakila test in `test_module.py`.

### [Scenario] S2: Master Failover (Orchestrator)
Terminate the master instance. Orchestrator detects failure, promotes a replica,
executes post-failover hooks (NLB write TG → new master, scale-in protection,
DynamoDB topology update, EC2 tag update). Write endpoint recovers. ASG replaces
the terminated instance; new instance joins as replica.
**Validates**: Orchestrator detection, automatic promotion, all failover hooks,
ASG self-healing, NLB continuity.

### [Scenario] S3: Replica Failure Recovery
Terminate a replica instance. ASG launches a replacement. New instance bootstraps
(Puppet, master discovery, CHANGE MASTER), joins replication, registers with read
target group. Read endpoint continues serving from remaining replicas during recovery.
**Validates**: ASG replacement, bootstrap on existing cluster, replication catch-up,
read TG registration.

### [Scenario] S4: Graceful Master Switchover
Operator performs planned maintenance: `orchestrator-client -c graceful-master-takeover`
to move master to a designated replica. Write endpoint continues serving. Old master
demoted to replica. Zero downtime.
**Validates**: Planned failover, NLB update, no data loss, continuous availability.

### [Scenario] S5: Version Upgrade (Rolling Refresh)
Deploy cluster on Percona 8.0. Change `percona_server_version` to 8.4. ASG instance
refresh replaces instances one at a time. Replication continues throughout (cross-version
GTID replication). All endpoints serve traffic during upgrade.
**Validates**: Version pinning, rolling upgrade, cross-version replication compatibility.

### [Scenario] S6: Backup and Restore
XtraBackup takes a full backup to S3. Verify backup exists in S3 with expected
structure. Restore backup to validate data consistency.
**Depends on**: Epic #5 (Backups). Create issue now, implement later.

### [Scenario] S7: Backup-Based Replica Bootstrap
A new replica joins the cluster by restoring from the latest S3 backup instead of
streaming from the master. Useful for large datasets where live streaming is too slow.
**Depends on**: Epic #5 (Backups). Create issue now, implement later.

### [Scenario] S8: Binlog Point-in-Time Recovery
Binlog archival streams to S3 in real-time. After a data loss event, restore from
last full backup + replay binlogs to a specific point in time.
**Depends on**: Epic #5 (Backups) + Epic #6 (Binlog Archival). Create issue now,
implement later.

## Priority Order

| Priority | Scenario | Testable Now? | Depends On |
|----------|----------|---------------|------------|
| 1        | S2: Master Failover | Yes | Orchestrator (done) |
| 2        | S3: Replica Failure | Yes | Bootstrap (done) |
| 3        | S4: Graceful Switchover | Yes | Orchestrator (done) |
| 4        | S5: Version Upgrade | Yes | Version control (done) |
| 5        | S6: Backup/Restore | No | Epic #5 |
| 6        | S7: Backup Bootstrap | No | Epic #5 |
| 7        | S8: PITR | No | Epic #5 + #6 |

S1 is already implemented. S2-S4 are immediately testable. S5 is testable but
expensive (full cluster re-deploy). S6-S8 are future work.

## Implementation

Create [Scenario] issues on GitHub, add them to the project board alongside
existing [Epic] issues. Each scenario issue describes:
- The user story (what happens)
- What it validates (which components/hooks)
- Test approach (how to implement in `test_module.py`)
- Dependencies (which epics must be done first)

Start implementing S2 (Master Failover) as the first test — it's the highest
value validation of the Orchestrator work just completed.