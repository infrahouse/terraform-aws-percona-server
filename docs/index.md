# terraform-aws-percona-server

Terraform module for deploying a highly available Percona Server cluster on AWS
with GTID-based replication, automatic failover via Orchestrator, and Raft-based
consensus for high availability.

## Features

- **High Availability**: Odd-number cluster (3, 5, 7+) with Orchestrator-managed
  automatic failover (~11s detection and promotion)
- **GTID Replication**: Global Transaction Identifiers for seamless failover positioning
- **Orchestrator + Raft**: Distributed Orchestrator cluster with Raft consensus
  for leader election and coordinated failover
- **Network Load Balancer**: Separate write (port 3306, master) and read
  (port 3307, replicas) endpoints with automatic updates on failover
- **ASG Lifecycle Hooks**: Lambda-based Raft peer management — automatically
  removes stale peers on termination, new instances join after bootstrap
- **Version Selection**: Deploy Percona Server 8.0 (default LTS) or 8.4 with
  rolling upgrades via ASG instance refresh
- **DynamoDB Locking**: Distributed locks for master election and backup coordination
- **Secrets Management**: MySQL credentials (root, replication, backup, monitor,
  orchestrator) stored in AWS Secrets Manager
- **S3 Backups**: Bucket with lifecycle policies ready for XtraBackup and binlog archival

## Quick Start

```hcl
module "percona" {
  source  = "infrahouse/percona-server/aws"
  version = "0.5.0"

  cluster_id     = "my-database"
  environment    = "production"
  subnet_ids     = ["subnet-abc123", "subnet-def456", "subnet-ghi789"]
  alarm_emails   = ["ops@example.com"]
  instance_count = 3
  instance_type  = "r6g.xlarge"
}

# Connect to the database
output "writer_endpoint" {
  value = module.percona.nlb_dns_name  # NLB:3306 -> master
}

output "reader_endpoint" {
  value = module.percona.nlb_dns_name  # NLB:3307 -> replicas
}
```

## Tested Scenarios

The following scenarios have been manually validated on real AWS infrastructure:

| Scenario | Description | Result |
|----------|-------------|--------|
| **S1: Fresh Cluster Deploy** | 3 instances, master election, GTID replication, NLB endpoints | Passing |
| **S2: Master Failover** | Terminate master, Orchestrator promotes replica in ~11s, ASG replaces instance | Passing |
| **S3: Replica Failure** | Terminate replica, ASG replacement joins replication automatically | Passing |
| **S4: Graceful Switchover** | `orchestrator-client -c graceful-master-takeover` — instant, zero downtime | Passing |

## Development Status

### Completed

- [x] **Infrastructure (Terraform)**
    - [x] Auto Scaling Group with launch template and rolling updates
    - [x] Network Load Balancer with write/read target groups
    - [x] DynamoDB table for coordination with TTL
    - [x] S3 bucket with lifecycle policies for backups
    - [x] Security groups for MySQL, Orchestrator HTTP/Raft, and internal traffic
    - [x] IAM roles and instance profiles with least-privilege permissions
    - [x] Secrets Manager integration for MySQL credentials
    - [x] Cloud-init integration with Puppet facts

- [x] **MySQL Configuration (Puppet)**
    - [x] Percona Server 8.0 and 8.4 installation with version pinning
    - [x] GTID-based replication setup
    - [x] User management (root, replication, backup, monitor, orchestrator)
    - [x] Target group registration (master -> write TG, replicas -> read TG)

- [x] **Orchestrator Integration**
    - [x] Orchestrator installation and Raft cluster setup
    - [x] Automated failover with DeadMaster detection
    - [x] Post-failover hooks (NLB, scale-in protection, DynamoDB, EC2 tags)
    - [x] Graceful master switchover support

- [x] **ASG Lifecycle Hooks**
    - [x] Lambda function for Raft peer management (terminate: remove stale peers)
    - [x] `raft-join.sh` script for new instance Raft join and cleanup
    - [x] EventBridge integration for lifecycle event routing

### Planned

- [ ] **Backup Automation**
    - [ ] Scheduled XtraBackup to S3
    - [ ] Binlog archival for point-in-time recovery
    - [ ] Backup-based replica bootstrap

- [ ] **Monitoring & Alerting**
    - [ ] CloudWatch metrics for replication lag
    - [ ] PMM integration
    - [ ] SNS alerts for failover events

## Why Self-Managed MySQL?

While AWS RDS provides a managed MySQL solution, self-managed Percona Server offers:

| Feature | RDS | Self-Managed Percona |
|---------|-----|---------------------|
| Cost | Higher | 50-70% savings |
| Root Access | No | Yes |
| Custom Plugins | Limited | Any |
| Instance Store | No | Yes (up to 3.3M IOPS) |
| Percona Toolkit | No | Yes |
| Full Control | No | Yes |

## Next Steps

- [Architecture](architecture.md) - Understand the infrastructure components
- [GitHub Repository](https://github.com/infrahouse/terraform-aws-percona-server) - Source code and issues
