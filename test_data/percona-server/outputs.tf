output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = module.percona-server.asg_name
}

output "nlb_dns_name" {
  description = "DNS name of the Network Load Balancer"
  value       = module.percona-server.nlb_dns_name
}

output "write_target_group_arn" {
  description = "ARN of the write target group"
  value       = module.percona-server.write_target_group_arn
}

output "read_target_group_arn" {
  description = "ARN of the read target group"
  value       = module.percona-server.read_target_group_arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = module.percona-server.dynamodb_table_name
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for backups"
  value       = module.percona-server.s3_bucket_name
}