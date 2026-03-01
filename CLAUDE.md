# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Steps

**Your first tool call in this repository MUST be reading .claude/CODING_STANDARD.md.
Do not read any other files, search, or take any actions until you have read it.**
This contains InfraHouse's comprehensive coding standards for Terraform, Python, and general formatting rules.

## Build and Test Commands

```bash
make bootstrap                              # Install Python deps (pip, setuptools, requirements.txt)
make format                                 # Format Terraform (terraform fmt -recursive) and Python (black tests)
make lint                                   # Check formatting without modifying files
make docs                                   # Regenerate terraform-docs in README.md
make test                                   # Full test suite (all AWS provider versions)
make test-keep                              # Run tests, keep infrastructure for debugging
make test-keep TEST_SELECTOR=aws-6          # Test only AWS provider v6
make test-keep TEST_SELECTOR=aws-5          # Test only AWS provider v5
make test-clean                             # Run tests and destroy resources (run before PRs)
make release-patch                          # Bump patch version, update CHANGELOG, create tag
```

Tests are parameterized pytest integration tests that deploy real AWS infrastructure. They run against both AWS provider v5 (`~> 5.62`) and v6 (`~> 6.0`). Test root module lives in `test_data/percona-server/`.

Default test config: `TEST_REGION=us-west-1`, `TEST_ROLE=arn:aws:iam::303467602807:role/percona-server-tester`.

## Architecture

This module deploys a highly available Percona Server (MySQL 8.0) cluster on AWS with GTID-based replication. Key components:

- **ASG** (`main.tf`): Launch template with IMDSv2 enforcement + Auto Scaling Group with rolling updates
- **NLB** (`nlb.tf`): Internal Network Load Balancer with write (port 3306, master) and read (port 3307, replicas) target groups
- **DynamoDB** (`dynamodb.tf`): Distributed locks and topology management with TTL
- **S3** (`s3.tf`): XtraBackup snapshots and binary log storage with lifecycle policies
- **Secrets** (`secrets.tf`): MySQL credentials (root, replication, backup, monitor) and LUKS passphrase via `infrahouse/secret/aws`
- **IAM** (`iam.tf`): Instance profile with least-privilege permissions for DynamoDB, S3, ASG, ELB, EC2
- **Cloud-init** (`cloud_init.tf`): Bootstrap via Puppet with custom facts passed through instance tags (prefixed `percona:`)
- **Security Groups** (`security_group.tf`): MySQL, Orchestrator HTTP/Raft, and ICMP rules

Storage type (EBS vs NVMe instance store) is auto-detected from the instance type in `locals.tf`.

### Module Dependencies

All InfraHouse modules use `registry.infrahouse.com` with exact version pinning:

- `infrahouse/instance-profile/aws` - IAM instance profile
- `infrahouse/cloud-init/aws` - Cloud-init + Puppet integration
- `infrahouse/s3-bucket/aws` - S3 with encryption/lifecycle
- `infrahouse/secret/aws` - Secrets Manager credentials

### Data Flow

- **Write path**: App -> NLB:3306 -> Write TG -> Master instance
- **Read path**: App -> NLB:3307 -> Read TG -> Replica instances
- **Replication**: Master -> Binary Log -> GTID Replication -> Replicas
- **Backup**: Master -> XtraBackup -> S3 (full + incremental, retention controlled by `backup_retention_weeks`)

## Key Conventions

- Module version tracked in `locals.tf` (`local.module_version`) and `.bumpversion.cfg`
- Instance count must be odd (3, 5, 7+) for quorum - enforced by variable validation
- Puppet facts are passed via EC2 instance tags (see `local.instance_tags` in `locals.tf`)
- `cancel_instance_refresh_on_error = true` in cloud-init prevents cascading ASG failures
- Checkov skip justifications are documented in `.checkov.yml`
- Max line length: 120 characters for all files
- All files must end with a newline