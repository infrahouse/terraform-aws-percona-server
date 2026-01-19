locals {
  environment = "development"
  # Static cluster_id to work around AWS provider 6.x bug where DynamoDB
  # DescribeTable is called with empty TableName when name depends on
  # an unknown value like random_pet.id.
  # See: https://github.com/hashicorp/terraform-provider-aws/issues/46016
  cluster_id = "test-percona"
}

resource "aws_key_pair" "test" {
  key_name   = "${local.cluster_id}-test-key"
  public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDpgAP1z1Lxg9Uv4tam6WdJBcAftZR4ik7RsSr6aNXqfnTj4civrhd/q8qMqF6wL//3OujVDZfhJcffTzPS2XYhUxh/rRVOB3xcqwETppdykD0XZpkHkc8XtmHpiqk6E9iBI4mDwYcDqEg3/vrDAGYYsnFwWmdDinxzMH1Gei+NPTmTqU+wJ1JZvkw3WBEMZKlUVJC/+nuv+jbMmCtm7sIM4rlp2wyzLWYoidRNMK97sG8+v+mDQol/qXK3Fuetj+1f+vSx2obSzpTxL4RYg1kS6W1fBlSvstDV5bQG4HvywzN5Y8eCpwzHLZ1tYtTycZEApFdy+MSfws5vPOpggQlWfZ4vA8ujfWAF75J+WABV4DlSJ3Ng6rLMW78hVatANUnb9s4clOS8H6yAjv+bU3OElKBkQ10wNneoFIMOA3grjPvPp5r8dI0WDXPIznJThDJO5yMCy3OfCXlu38VDQa1sjVj1zAPG+Vn2DsdVrl50hWSYSB17Zww0MYEr8N5rfFE= aleks@MediaPC"
}

module "percona-server" {
  source = "../.."

  cluster_id       = local.cluster_id
  environment      = local.environment
  subnet_ids       = var.subnet_ids
  instance_count   = 3
  instance_type    = "t3.medium"
  s3_force_destroy = true
  key_name         = aws_key_pair.test.key_name
}
