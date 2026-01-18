# terraform-aws-percona-server

[![Need Help?](https://img.shields.io/badge/Need%20Help%3F-Contact%20Us-0066CC)](https://infrahouse.com/contact)
[![Docs](https://img.shields.io/badge/docs-github.io-blue)](https://infrahouse.github.io/terraform-aws-percona-server/)
[![Registry](https://img.shields.io/badge/Terraform-Registry-purple?logo=terraform)](https://registry.terraform.io/modules/infrahouse/percona-server/aws/latest)
[![Release](https://img.shields.io/github/release/infrahouse/terraform-aws-percona-server.svg)](https://github.com/infrahouse/terraform-aws-percona-server/releases/latest)
[![AWS EC2](https://img.shields.io/badge/AWS-EC2-orange?logo=amazonec2)](https://aws.amazon.com/ec2/)
[![AWS RDS](https://img.shields.io/badge/AWS-DynamoDB-orange?logo=amazondynamodb)](https://aws.amazon.com/dynamodb/)
[![AWS S3](https://img.shields.io/badge/AWS-S3-orange?logo=amazons3)](https://aws.amazon.com/s3/)
[![Security](https://img.shields.io/github/actions/workflow/status/infrahouse/terraform-aws-percona-server/vuln-scanner-pr.yml?label=Security)](https://github.com/infrahouse/terraform-aws-percona-server/actions/workflows/vuln-scanner-pr.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Terraform module for Percona Server replica set with GTID replication, Orchestrator HA, and automated failover.

## Features

- **High Availability**: Odd-number cluster with automatic master election
- **GTID Replication**: Automatic positioning for seamless failover
- **Orchestrator HA**: Raft-based consensus for automated failover
- **Network Load Balancer**: Separate write (master) and read (replica) endpoints
- **Automated Backups**: XtraBackup with S3 storage and configurable retention
- **Binlog Archival**: Real-time streaming for point-in-time recovery
- **DynamoDB Locking**: Distributed locks for master election and backup coordination

## Quick Start

```hcl
module "percona" {
  source  = "infrahouse/percona-server/aws"
  version = "~> 0.1"

  cluster_id     = "my-database"
  environment    = "production"
  subnet_ids     = ["subnet-abc123", "subnet-def456", "subnet-ghi789"]
  instance_count = 3
  instance_type  = "r6g.xlarge"
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Single ASG                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Percona   │  │   Percona   │  │   Percona   │     │
│  │   Master    │  │   Replica   │  │   Replica   │     │
│  │ (protected) │  │             │  │             │     │
│  │ Orchestrator│  │ Orchestrator│  │ Orchestrator│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
         │                                    │
         │ write TG (3306)                   │ read TG (3307)
         ▼                                    ▼
┌─────────────────────────────────────────────────────────┐
│                         NLB                             │
└─────────────────────────────────────────────────────────┘
```

## Documentation

- [Getting Started](https://infrahouse.github.io/terraform-aws-percona-server/getting-started/)
- [Configuration](https://infrahouse.github.io/terraform-aws-percona-server/configuration/)
- [Architecture](https://infrahouse.github.io/terraform-aws-percona-server/architecture/)

## Requirements

| Name | Version |
|------|---------|
| terraform | ~> 1.5 |
| aws | ~> 5.62 |

<!-- BEGIN_TF_DOCS -->

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.5 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 5.62, < 7.0 |
| <a name="requirement_random"></a> [random](#requirement\_random) | ~> 3.6 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | >= 5.62, < 7.0 |
| <a name="provider_random"></a> [random](#provider\_random) | ~> 3.6 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_backups"></a> [backups](#module\_backups) | registry.infrahouse.com/infrahouse/s3-bucket/aws | 0.3.1 |
| <a name="module_instance_profile"></a> [instance\_profile](#module\_instance\_profile) | registry.infrahouse.com/infrahouse/instance-profile/aws | 1.9.0 |
| <a name="module_luks_passphrase"></a> [luks\_passphrase](#module\_luks\_passphrase) | registry.infrahouse.com/infrahouse/secret/aws | 1.1.1 |

## Resources

| Name | Type |
|------|------|
| [aws_autoscaling_group.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group) | resource |
| [aws_dynamodb_table.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table) | resource |
| [aws_launch_template.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template) | resource |
| [aws_lb.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb) | resource |
| [aws_lb_listener.read](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener) | resource |
| [aws_lb_listener.write](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener) | resource |
| [aws_lb_target_group.read](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group) | resource |
| [aws_lb_target_group.write](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group) | resource |
| [aws_s3_bucket_lifecycle_configuration.backups](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration) | resource |
| [aws_security_group.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_vpc_security_group_egress_rule.all_outbound](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_egress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.icmp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.mysql_client_cidr](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.mysql_client_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.mysql_internal](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.mysql_vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.orchestrator_http](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.orchestrator_raft](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_security_group_ingress_rule) | resource |
| [random_password.luks_passphrase](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password) | resource |
| [aws_ami.selected](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_ami.ubuntu](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_ec2_instance_type.selected](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ec2_instance_type) | data source |
| [aws_iam_policy_document.percona](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |
| [aws_subnet.selected](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |
| [aws_vpc.selected](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ami_id"></a> [ami\_id](#input\_ami\_id) | AMI ID for the Percona instances. If not specified, the latest Ubuntu Pro AMI for var.ubuntu\_codename will be used.<br/>Set to null to use the default Ubuntu AMI. | `string` | `null` | no |
| <a name="input_backup_retention_weeks"></a> [backup\_retention\_weeks](#input\_backup\_retention\_weeks) | Number of weeks to retain backups in S3 | `number` | `4` | no |
| <a name="input_client_cidrs"></a> [client\_cidrs](#input\_client\_cidrs) | List of CIDR blocks allowed to connect to MySQL. If both this and client\_security\_group\_ids are empty, VPC CIDR is used. | `list(string)` | `[]` | no |
| <a name="input_client_security_group_ids"></a> [client\_security\_group\_ids](#input\_client\_security\_group\_ids) | List of security group IDs allowed to connect to MySQL. If both this and client\_cidrs are empty, VPC CIDR is used. | `list(string)` | `[]` | no |
| <a name="input_cluster_id"></a> [cluster\_id](#input\_cluster\_id) | Unique identifier for the Percona cluster | `string` | n/a | yes |
| <a name="input_environment"></a> [environment](#input\_environment) | Environment name (development, staging, production, etc.) | `string` | n/a | yes |
| <a name="input_instance_count"></a> [instance\_count](#input\_instance\_count) | Number of instances in the cluster (must be odd, minimum 3) | `number` | `3` | no |
| <a name="input_instance_type"></a> [instance\_type](#input\_instance\_type) | EC2 instance type for the Percona nodes | `string` | `"t3.medium"` | no |
| <a name="input_root_volume_size"></a> [root\_volume\_size](#input\_root\_volume\_size) | Size of the root EBS volume in GB | `number` | `100` | no |
| <a name="input_s3_force_destroy"></a> [s3\_force\_destroy](#input\_s3\_force\_destroy) | Allow the S3 bucket to be destroyed even if it contains objects. Set to true for testing. | `bool` | `false` | no |
| <a name="input_subnet_ids"></a> [subnet\_ids](#input\_subnet\_ids) | List of subnet IDs for the Auto Scaling Group | `list(string)` | n/a | yes |
| <a name="input_tags"></a> [tags](#input\_tags) | Additional tags to apply to all resources | `map(string)` | `{}` | no |
| <a name="input_ubuntu_codename"></a> [ubuntu\_codename](#input\_ubuntu\_codename) | Ubuntu version codename to use for the Percona instances. Only LTS versions are supported. | `string` | `"noble"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_asg_arn"></a> [asg\_arn](#output\_asg\_arn) | ARN of the Auto Scaling Group |
| <a name="output_asg_name"></a> [asg\_name](#output\_asg\_name) | Name of the Auto Scaling Group |
| <a name="output_dynamodb_table_arn"></a> [dynamodb\_table\_arn](#output\_dynamodb\_table\_arn) | ARN of the DynamoDB table |
| <a name="output_dynamodb_table_name"></a> [dynamodb\_table\_name](#output\_dynamodb\_table\_name) | Name of the DynamoDB table for locks and topology |
| <a name="output_instance_profile_name"></a> [instance\_profile\_name](#output\_instance\_profile\_name) | Name of the IAM instance profile |
| <a name="output_instance_role_arn"></a> [instance\_role\_arn](#output\_instance\_role\_arn) | ARN of the IAM role attached to Percona instances |
| <a name="output_luks_passphrase_secret_arn"></a> [luks\_passphrase\_secret\_arn](#output\_luks\_passphrase\_secret\_arn) | ARN of the Secrets Manager secret containing LUKS passphrase (only for instance\_store) |
| <a name="output_nlb_arn"></a> [nlb\_arn](#output\_nlb\_arn) | ARN of the Network Load Balancer |
| <a name="output_nlb_dns_name"></a> [nlb\_dns\_name](#output\_nlb\_dns\_name) | DNS name of the Network Load Balancer |
| <a name="output_read_target_group_arn"></a> [read\_target\_group\_arn](#output\_read\_target\_group\_arn) | ARN of the read (replica) target group |
| <a name="output_reader_endpoint"></a> [reader\_endpoint](#output\_reader\_endpoint) | MySQL reader endpoint (replicas) - host:port |
| <a name="output_s3_bucket_arn"></a> [s3\_bucket\_arn](#output\_s3\_bucket\_arn) | ARN of the S3 bucket |
| <a name="output_s3_bucket_name"></a> [s3\_bucket\_name](#output\_s3\_bucket\_name) | Name of the S3 bucket for backups and binlogs |
| <a name="output_security_group_id"></a> [security\_group\_id](#output\_security\_group\_id) | ID of the Percona cluster security group |
| <a name="output_storage_type"></a> [storage\_type](#output\_storage\_type) | Storage type used for MySQL data: 'ebs' or 'instance\_store' |
| <a name="output_write_target_group_arn"></a> [write\_target\_group\_arn](#output\_write\_target\_group\_arn) | ARN of the write (master) target group |
| <a name="output_writer_endpoint"></a> [writer\_endpoint](#output\_writer\_endpoint) | MySQL writer endpoint (master) - host:port |
<!-- END_TF_DOCS -->

## Examples

See the [examples/](examples/) directory for complete usage examples.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

Apache 2.0 Licensed. See [LICENSE](LICENSE) for full details.
