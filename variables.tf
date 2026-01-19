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

variable "puppet_role" {
  description = <<-EOT
    Puppet role for the Percona instances. Passed as a puppet fact.
    Must contain only lowercase letters, numbers, and underscores (no hyphens).
  EOT
  type        = string
  default     = "percona_server"

  validation {
    condition     = can(regex("^[a-z0-9_]+$", var.puppet_role))
    error_message = "puppet_role must contain only lowercase letters, numbers, and underscores (no hyphens). Got: ${var.puppet_role}"
  }
}

variable "puppet_debug_logging" {
  description = "Enable Puppet debug logging during bootstrap."
  type        = bool
  default     = false
}

variable "puppet_environmentpath" {
  description = "A path for directory environments."
  type        = string
  default     = "{root_directory}/environments"
}

variable "puppet_hiera_config_path" {
  description = "Path to hiera configuration file."
  type        = string
  default     = "{root_directory}/environments/{environment}/hiera.yaml"
}

variable "puppet_manifest" {
  description = "Path to puppet manifest. By default ih-puppet will apply {root_directory}/environments/{environment}/manifests/site.pp."
  type        = string
  default     = null
}

variable "puppet_module_path" {
  description = "Path to common puppet modules."
  type        = string
  default     = "{root_directory}/environments/{environment}/modules:{root_directory}/modules"
}

variable "puppet_root_directory" {
  description = "Path where the puppet code is hosted."
  type        = string
  default     = "/opt/puppet-code"
}

variable "puppet_custom_facts" {
  description = <<-EOF
    A map of custom puppet facts. The module uses deep merge to combine user facts
    with module-managed facts. User-provided values take precedence on conflicts.

    Module automatically provides percona-specific facts for cluster configuration.
  EOF
  type        = any
  default     = {}
}

variable "extra_packages" {
  description = "Additional packages to install during instance bootstrap."
  type        = list(string)
  default     = []
}

variable "key_name" {
  description = "Name of the EC2 key pair for SSH access to instances. If null, no key pair is assigned."
  type        = string
  default     = null
}