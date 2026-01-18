locals {
  environment = "development"
  # Static cluster_id to work around AWS provider 6.x bug where DynamoDB
  # DescribeTable is called with empty TableName when name depends on
  # an unknown value like random_pet.id.
  # See: https://github.com/hashicorp/terraform-provider-aws/issues/46016
  cluster_id = "test-percona"
}

module "percona-server" {
  source = "../.."

  cluster_id       = local.cluster_id
  environment      = local.environment
  subnet_ids       = var.subnet_ids
  instance_count   = 3
  instance_type    = "t3.medium"
  s3_force_destroy = true
}