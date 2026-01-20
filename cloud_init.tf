# Cloud-init configuration for Percona instances
module "cloud_init" {
  source  = "registry.infrahouse.com/infrahouse/cloud-init/aws"
  version = "2.2.3"

  environment     = var.environment
  role            = var.puppet_role
  ubuntu_codename = var.ubuntu_codename

  # Pass Percona cluster configuration as custom Puppet facts
  # Deep merge to preserve any user-provided facts
  # User's input has precedence on conflicts
  # Note: ASG name is discovered from instance metadata (aws:autoscaling:groupName tag)
  custom_facts = merge(
    var.puppet_custom_facts,
    {
      percona = merge(
        {
          cluster_id         = var.cluster_id
          dynamodb_table     = aws_dynamodb_table.percona.name
          s3_bucket          = module.backups.bucket_name
          write_tg_arn       = aws_lb_target_group.write.arn
          read_tg_arn        = aws_lb_target_group.read.arn
          instance_count     = var.instance_count
          storage_type       = local.storage_type
          storage_size       = local.use_instance_store ? local.instance_store_size : var.root_volume_size
          credentials_secret = module.mysql_credentials.secret_name
          vpc_cidr           = data.aws_vpc.selected.cidr_block
        },
        lookup(var.puppet_custom_facts, "percona", {})
      )
    }
  )

  packages = var.extra_packages

  puppet_debug_logging     = var.puppet_debug_logging
  puppet_environmentpath   = var.puppet_environmentpath
  puppet_hiera_config_path = var.puppet_hiera_config_path
  puppet_manifest          = var.puppet_manifest
  puppet_module_path       = var.puppet_module_path
  puppet_root_directory    = var.puppet_root_directory

  # CRITICAL: Stop instance refresh if provisioning fails.
  # Lesson learned from Elasticsearch cluster data loss: when a new instance
  # fails to provision properly, AWS continues the rolling refresh and replaces
  # all nodes with empty/broken instances. This setting ensures the refresh
  # stops on first failure, preserving the remaining healthy nodes with data.
  cancel_instance_refresh_on_error = true
}
