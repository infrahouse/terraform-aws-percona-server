# Architecture

This page describes the AWS infrastructure components deployed by the terraform-aws-percona-server module.

## Overview

![Architecture Diagram](assets/architecture.png)

The module deploys a highly available MySQL cluster using Percona Server 8.0 with GTID-based replication. All components are deployed within your VPC for security and low latency.

## Components

### Network Load Balancer

The internal NLB provides two endpoints for database connections:

| Endpoint | Port | Target | Use Case |
|----------|------|--------|----------|
| Write | 3306 | Master only | INSERT, UPDATE, DELETE, transactions |
| Read | 3307 | All replicas | SELECT queries, reporting |

**Benefits:**

- Layer 4 load balancing with minimal latency
- Health checks ensure traffic only goes to healthy instances
- Automatic failover when master changes (via target group updates)

### Auto Scaling Group

The ASG manages the EC2 instances running Percona Server:

- **Instance Count**: Always odd (3, 5, 7) for quorum-based decisions
- **Rolling Updates**: Configuration changes trigger instance refresh
- **Self-Healing**: Unhealthy instances are automatically replaced
- **Launch Template**: Defines instance configuration, user data, and tags

### EC2 Instances

Each instance runs:

- **Percona Server 8.0**: MySQL-compatible database with performance enhancements
- **GTID Replication**: Global Transaction Identifiers for consistent replication
- **Puppet Agent**: Configuration management via cloud-init bootstrap

**Instance Types:**

| Type | Use Case | Storage |
|------|----------|---------|
| `t3.medium` | Development/testing | EBS only |
| `r6g.xlarge` | Production (memory-optimized) | EBS only |
| `i3en.xlarge` | High-IOPS workloads | NVMe instance store |

### DynamoDB Table

Used for distributed coordination:

| Item Type | Purpose |
|-----------|---------|
| `master_lock` | Ensures single master election |
| `topology` | Stores cluster topology information |
| `backup_lock` | Prevents concurrent backup operations |

**Features:**

- On-demand capacity (pay per request)
- TTL-enabled for automatic cleanup of stale locks
- Point-in-time recovery enabled

### S3 Bucket

Stores backups and binary logs:

```
s3://percona-{cluster_id}-backups/
├── {cluster_id}/
│   ├── full/           # Full XtraBackup snapshots
│   ├── incremental/    # Incremental backups
│   └── binlogs/        # Archived binary logs
```

**Lifecycle Policies:**

- Full backups: Retained for `backup_retention_weeks`
- Incremental backups: Same retention as full
- Binary logs: Same retention as full
- Non-current versions: Deleted after 7 days

### Secrets Manager

Stores sensitive credentials:

| Secret | Contents |
|--------|----------|
| `{cluster_id}/mysql-credentials` | root, replication, backup, monitor passwords |
| `{cluster_id}-luks-*` | LUKS passphrase (instance store only) |

### Security Groups

Controls network access:

| Rule | Port | Source | Purpose |
|------|------|--------|---------|
| MySQL (clients) | 3306 | VPC CIDR or specified | Application connections |
| MySQL (internal) | 3306 | Self | Replication traffic |
| Orchestrator HTTP | 3000 | Self | Web UI and API |
| Orchestrator Raft | 10008 | Self | Raft consensus |
| ICMP | - | VPC CIDR | Health checks |

## Data Flow

### Write Path

```
Application
    │
    ▼
NLB (port 3306)
    │
    ▼
Write Target Group
    │
    ▼
Master Instance ───────► DynamoDB (topology)
    │
    ▼
Binary Log
    │
    ▼
Replicas (GTID replication)
```

### Read Path

```
Application
    │
    ▼
NLB (port 3307)
    │
    ▼
Read Target Group
    │
    ├───► Replica 1
    └───► Replica 2
```

### Backup Path

```
Master Instance
    │
    ▼
XtraBackup
    │
    ▼
S3 Bucket (full/)
    │
    ▼
Lifecycle Policy ───► Expiration
```

## Replication

### GTID (Global Transaction Identifiers)

Each transaction is assigned a unique identifier:

```
server_uuid:transaction_id
Example: bf30f9b7-f4de-11f0-8310-06ed89e4c4bd:1-13
```

**Benefits:**

- Automatic positioning during failover
- No need to track binlog file/position
- Consistent replication state across all replicas

### Topology

```
        ┌─────────────┐
        │   Master    │
        │  (RW + TG)  │
        └──────┬──────┘
               │ GTID Replication
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐ ┌─────────────┐
│  Replica 1  │ │  Replica 2  │
│  (RO + TG)  │ │  (RO + TG)  │
└─────────────┘ └─────────────┘
```

- **RW**: Read-Write (master)
- **RO**: Read-Only (replicas)
- **TG**: Target Group (write for master, read for replicas)

## High Availability

### Current Implementation

- GTID replication ensures data consistency
- NLB health checks detect failures quickly (10s interval)
- Target group deregistration delay: 30s for fast failover
- Manual failover by updating target group registrations

### Planned (Orchestrator)

- Automatic topology detection
- Automated failover with configurable policies
- Raft consensus for HA Orchestrator cluster
- Web UI for monitoring and manual operations

## Security

### Network Security

- All instances in private subnets
- No public IPs assigned
- Access via SSM Session Manager (no SSH bastion needed)
- Security groups restrict traffic to VPC CIDR

### Data Security

- EBS volumes encrypted at rest
- Instance store encrypted with LUKS (passphrase in Secrets Manager)
- MySQL credentials in Secrets Manager
- IAM roles with least-privilege permissions

### Compliance

- All resources tagged for cost allocation
- CloudTrail logging for API calls
- VPC Flow Logs compatible
