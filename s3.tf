# S3 bucket for backups and binlogs
module "backups" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.3.1"

  bucket_prefix     = "${local.name_prefix}-backups-"
  enable_versioning = true
  force_destroy     = var.s3_force_destroy

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-backups"
    }
  )
}

# Lifecycle policy for backup retention
resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = module.backups.bucket_name

  rule {
    id     = "full-backup-retention"
    status = "Enabled"

    filter {
      prefix = "${var.cluster_id}/full/"
    }

    expiration {
      days = var.backup_retention_weeks * 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "incremental-backup-retention"
    status = "Enabled"

    filter {
      prefix = "${var.cluster_id}/incremental/"
    }

    expiration {
      days = var.backup_retention_weeks * 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "binlog-retention"
    status = "Enabled"

    filter {
      prefix = "${var.cluster_id}/binlogs/"
    }

    expiration {
      days = var.backup_retention_weeks * 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}
