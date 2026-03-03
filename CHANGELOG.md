# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-03-03

### Documentation

- Update docs with Orchestrator, lifecycle hooks, and tested scenarios

### Features

- Add percona_server_version variable for version control
- Add Raft lifecycle hooks for Orchestrator peer management

### Miscellaneous Tasks

- Fix & ignore local reviews
- Skip CKV2_AWS_5 for Lambda security group attached via module

## [0.3.0] - 2026-03-01

### Bug Fixes

- Add error handling to release targets

### Features

- Complete Infrastructure and Puppet Integration epics
- Add IAM permissions for bootstrap and fix dependency cycle ([#3](https://github.com/infrahouse/terraform-aws-percona-server/issues/3)) ([#36](https://github.com/infrahouse/terraform-aws-percona-server/issues/36))
- Add end-to-end Sakila integration test ([#3](https://github.com/infrahouse/terraform-aws-percona-server/issues/3))

### Miscellaneous Tasks

- Update terraform registry.infrahouse.com/infrahouse/cloud-init/aws to v2.2.3
- Add checkov config and fix security findings

## [0.3.0] - 2026-03-01

### Features

- Complete Infrastructure and Puppet Integration epics
- Add IAM permissions for bootstrap and fix dependency cycle ([#3](https://github.com/infrahouse/terraform-aws-percona-server/issues/3)) ([#36](https://github.com/infrahouse/terraform-aws-percona-server/issues/36))
- Add end-to-end Sakila integration test ([#3](https://github.com/infrahouse/terraform-aws-percona-server/issues/3))

### Miscellaneous Tasks

- Update terraform registry.infrahouse.com/infrahouse/cloud-init/aws to v2.2.3
- Add checkov config and fix security findings

## [0.2.0] - 2026-01-19

### Bug Fixes

- Address PR review feedback for infrastructure improvements

### Features

- Implement core infrastructure for Percona Server cluster
- Complete Infrastructure and Puppet Integration epics

## [Unreleased]

### Added

- Initial module structure with Infrastructure components (Epic #2)
- Auto Scaling Group with odd-number validation and ELB health checks
- Network Load Balancer with separate write/read target groups
- DynamoDB table for distributed locks and topology storage
- S3 bucket for backups and binlogs with lifecycle policies
- IAM roles and policies for instance permissions
- Security groups for MySQL and Orchestrator traffic
- Makefile with standard targets (test, test-keep, test-clean, etc.)
- Pytest integration tests for AWS provider versions 5 and 6
