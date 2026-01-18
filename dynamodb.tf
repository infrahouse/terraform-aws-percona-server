# DynamoDB table for distributed locks and cluster topology
#
# Keys stored in this table:
#   lock-{cluster_id}          - Master election lock (uses TTL for auto-expiration)
#   topology-{cluster_id}      - Master info (instance_id, private_ip) - no TTL
#   backup-lock-{cluster_id}   - Backup leader election (uses TTL for auto-expiration)
#   binlog-lock-{cluster_id}   - Binlog streaming leader election (uses TTL for auto-expiration)
#   binlog-position-{cluster_id} - Last synced GTID position - no TTL
#
# Lock items include a 'ttl' attribute (Unix timestamp) for automatic expiration
# if the lock holder dies without releasing. Topology/position records are permanent.
resource "aws_dynamodb_table" "percona" {
  name         = "${local.name_prefix}-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  # TTL for automatic lock expiration when holder dies without releasing
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-locks"
    }
  )
}
