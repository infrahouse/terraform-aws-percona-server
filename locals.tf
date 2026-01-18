locals {
  name_prefix = "percona-${var.cluster_id}"

  lts_codenames = ["noble"]

  ami_name_pattern = contains(local.lts_codenames, var.ubuntu_codename) ? (
    "ubuntu-pro-server/images/hvm-ssd-gp3/ubuntu-${var.ubuntu_codename}-*"
    ) : (
    "ubuntu/images/hvm-ssd-gp3/ubuntu-${var.ubuntu_codename}-*"
  )

  ami_id = var.ami_id == null ? data.aws_ami.ubuntu[0].id : var.ami_id

  # Storage type detection based on instance type capabilities
  # If instance has local NVMe SSD, use instance_store; otherwise use EBS
  # Note: instance_disks is a set, so we convert to list for indexing
  instance_disks_list = tolist(data.aws_ec2_instance_type.selected.instance_disks)
  has_instance_store  = length(local.instance_disks_list) > 0
  instance_store_is_ssd = local.has_instance_store ? (
    local.instance_disks_list[0].type == "ssd"
  ) : false
  use_instance_store = local.has_instance_store && local.instance_store_is_ssd

  # Storage details for Puppet
  storage_type = local.use_instance_store ? "instance_store" : "ebs"

  # Instance store details (when applicable)
  instance_store_count = local.use_instance_store ? local.instance_disks_list[0].count : 0
  instance_store_size  = local.use_instance_store ? local.instance_disks_list[0].size : 0

  # Root volume size: smaller when using instance store for data
  root_volume_size = local.use_instance_store ? 20 : var.root_volume_size

  common_tags = merge(
    var.tags,
    {
      environment       = var.environment
      cluster_id        = var.cluster_id
      created_by_module = "infrahouse/percona-server/aws"
    }
  )

  # Instance tags for Puppet custom facts
  instance_tags = {
    "percona:cluster_id"      = var.cluster_id
    "percona:dynamodb_table"  = aws_dynamodb_table.percona.name
    "percona:s3_bucket"       = module.backups.bucket_name
    "percona:write_tg_arn"    = aws_lb_target_group.write.arn
    "percona:read_tg_arn"     = aws_lb_target_group.read.arn
    "percona:asg_name"        = "${local.name_prefix}-asg"
    "percona:instance_count"  = var.instance_count
    "percona:storage_type"    = local.storage_type
    "percona:storage_size_gb" = local.use_instance_store ? local.instance_store_size : var.root_volume_size
    "percona:storage_count"   = local.instance_store_count
    "percona:luks_key_arn"    = local.use_instance_store ? module.luks_passphrase[0].secret_arn : ""
  }
}