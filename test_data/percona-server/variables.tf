variable "region" {
  description = "AWS region"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN to assume"
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "List of subnet IDs for the cluster"
  type        = list(string)
}

variable "percona_server_version" {
  description = "Percona Server version to install"
  type        = string
  default     = null
}

variable "alarm_emails" {
  description = "Email addresses for Lambda monitoring alarms"
  type        = list(string)
  default     = ["aleks+terraform-aws-percona-server@infrahouse.com"]
}
