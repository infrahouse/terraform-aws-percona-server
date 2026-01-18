variable "cluster_id" {
  description = "Unique identifier for the Percona cluster"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.cluster_id))
    error_message = "cluster_id must contain only lowercase letters, numbers, and hyphens"
  }
}

variable "environment" {
  description = "Environment name (development, staging, production, etc.)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.environment))
    error_message = "environment must contain only lowercase letters, numbers, and underscores"
  }
}

variable "instance_count" {
  description = "Number of instances in the cluster (must be odd, minimum 3)"
  type        = number
  default     = 3

  validation {
    condition     = var.instance_count >= 3 && var.instance_count % 2 == 1
    error_message = "instance_count must be an odd number >= 3. Got: ${var.instance_count}"
  }
}

variable "instance_type" {
  description = "EC2 instance type for the Percona nodes"
  type        = string
  default     = "t3.medium"
}

variable "subnet_ids" {
  description = "List of subnet IDs for the Auto Scaling Group"
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 1
    error_message = "At least 1 subnet is required"
  }
}

variable "backup_retention_weeks" {
  description = "Number of weeks to retain backups in S3"
  type        = number
  default     = 4

  validation {
    condition     = var.backup_retention_weeks >= 1 && var.backup_retention_weeks <= 52
    error_message = "backup_retention_weeks must be between 1 and 52. Got: ${var.backup_retention_weeks}"
  }
}

variable "root_volume_size" {
  description = "Size of the root EBS volume in GB"
  type        = number
  default     = 100

  validation {
    condition     = var.root_volume_size >= 20
    error_message = "root_volume_size must be at least 20 GB"
  }
}

variable "ami_id" {
  description = <<-EOT
    AMI ID for the Percona instances. If not specified, the latest Ubuntu Pro AMI for var.ubuntu_codename will be used.
    Set to null to use the default Ubuntu AMI.
  EOT
  type        = string
  default     = null
}

variable "ubuntu_codename" {
  description = "Ubuntu version codename to use for the Percona instances. Only LTS versions are supported."
  type        = string
  default     = "noble"

  validation {
    condition     = contains(["noble"], var.ubuntu_codename)
    error_message = "Only Ubuntu LTS versions are supported. Currently supported: noble."
  }
}

variable "s3_force_destroy" {
  description = "Allow the S3 bucket to be destroyed even if it contains objects. Set to true for testing."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "client_security_group_ids" {
  description = "List of security group IDs allowed to connect to MySQL. If both this and client_cidrs are empty, VPC CIDR is used."
  type        = list(string)
  default     = []
}

variable "client_cidrs" {
  description = "List of CIDR blocks allowed to connect to MySQL. If both this and client_security_group_ids are empty, VPC CIDR is used."
  type        = list(string)
  default     = []
}