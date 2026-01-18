# LUKS passphrase secret for instance store encryption
# Only created when using instance store (local NVMe SSD)

resource "random_password" "luks_passphrase" {
  count   = local.use_instance_store ? 1 : 0
  length  = 64
  special = false
}

module "luks_passphrase" {
  count              = local.use_instance_store ? 1 : 0
  source             = "registry.infrahouse.com/infrahouse/secret/aws"
  version            = "1.1.1"
  environment        = var.environment
  secret_description = "LUKS passphrase for Percona cluster ${var.cluster_id} instance store encryption"
  secret_name_prefix = "${local.name_prefix}-luks-"
  secret_value       = random_password.luks_passphrase[0].result
  tags               = local.common_tags
  readers = [
    module.instance_profile.instance_role_arn
  ]
}