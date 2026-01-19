# terraform-aws-percona-server

Terraform module for deploying a highly available Percona Server (MySQL 8.0) cluster on AWS with GTID-based replication, automatic failover, and automated backups.

!!! warning "Work in Progress"
    This module is under active development. Core infrastructure is complete and tested. See [Development Status](#development-status) for details.

## Features

- **High Availability**: Odd-number cluster with automatic master election
- **GTID Replication**: Automatic positioning for seamless failover
- **Network Load Balancer**: Separate write (master) and read (replica) endpoints
- **Automated Backups**: XtraBackup with S3 storage and configurable retention
- **DynamoDB Locking**: Distributed locks for master election and backup coordination
- **Secrets Management**: MySQL credentials stored securely in AWS Secrets Manager

## Quick Start

```hcl
module "percona" {
  source  = "infrahouse/percona-server/aws"
  version = "0.1.0"

  cluster_id     = "my-database"
  environment    = "production"
  subnet_ids     = ["subnet-abc123", "subnet-def456", "subnet-ghi789"]
  instance_count = 3
  instance_type  = "r6g.xlarge"
}

# Connect to the database
output "writer_endpoint" {
  value = module.percona.writer_endpoint  # NLB:3306 -> master
}

output "reader_endpoint" {
  value = module.percona.reader_endpoint  # NLB:3307 -> replicas
}
```

## Development Status

### Completed

- [x] **Infrastructure (Terraform)**
    - [x] Auto Scaling Group with launch template
    - [x] Network Load Balancer with write/read target groups
    - [x] DynamoDB table for coordination
    - [x] S3 bucket with lifecycle policies for backups
    - [x] Security groups for MySQL, Orchestrator, and internal traffic
    - [x] IAM roles and instance profiles
    - [x] Secrets Manager integration for MySQL credentials
    - [x] Cloud-init integration with Puppet facts

- [x] **MySQL Configuration (Puppet)**
    - [x] Percona Server 8.0 installation
    - [x] GTID-based replication setup
    - [x] User management (root, replication, backup, monitor)
    - [x] Target group registration (master -> write TG, replicas -> read TG)

### In Progress

- [ ] **Orchestrator Integration**
    - [ ] Orchestrator installation and Raft cluster setup
    - [ ] Automated failover with topology detection
    - [ ] Web UI for cluster visualization

### Planned

- [ ] **Backup Automation**
    - [ ] Scheduled XtraBackup to S3
    - [ ] Binlog archival for point-in-time recovery

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
