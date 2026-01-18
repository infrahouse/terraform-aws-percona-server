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
