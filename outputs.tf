output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.percona.name
}

output "asg_arn" {
  description = "ARN of the Auto Scaling Group"
  value       = aws_autoscaling_group.percona.arn
}

output "nlb_arn" {
  description = "ARN of the Network Load Balancer"
  value       = aws_lb.percona.arn
}

output "nlb_dns_name" {
  description = "DNS name of the Network Load Balancer"
  value       = aws_lb.percona.dns_name
}

output "writer_endpoint" {
  description = "MySQL writer endpoint (master) - host:port"
  value       = "${aws_lb.percona.dns_name}:${aws_lb_listener.write.port}"
}

output "reader_endpoint" {
  description = "MySQL reader endpoint (replicas) - host:port"
  value       = "${aws_lb.percona.dns_name}:${aws_lb_listener.read.port}"
}

output "write_target_group_arn" {
  description = "ARN of the write (master) target group"
  value       = aws_lb_target_group.write.arn
}

output "read_target_group_arn" {
  description = "ARN of the read (replica) target group"
  value       = aws_lb_target_group.read.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for locks and topology"
  value       = aws_dynamodb_table.percona.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.percona.arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for backups and binlogs"
  value       = module.backups.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.backups.bucket_arn
}

output "security_group_id" {
  description = "ID of the Percona cluster security group"
  value       = aws_security_group.percona.id
}

output "instance_role_arn" {
  description = "ARN of the IAM role attached to Percona instances"
  value       = module.instance_profile.instance_role_arn
}

output "instance_profile_name" {
  description = "Name of the IAM instance profile"
  value       = module.instance_profile.instance_profile_name
}

output "storage_type" {
  description = "Storage type used for MySQL data: 'ebs' or 'instance_store'"
  value       = local.storage_type
}

output "luks_passphrase_secret_arn" {
  description = "ARN of the Secrets Manager secret containing LUKS passphrase (only for instance_store)"
  value       = local.use_instance_store ? module.luks_passphrase[0].secret_arn : null
}