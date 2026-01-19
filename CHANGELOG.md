# Changelog

All notable changes to this project will be documented in this file.

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
