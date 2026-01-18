resource "aws_security_group" "percona" {
  name_prefix = "${local.name_prefix}-"
  description = "Security group for Percona Server cluster ${var.cluster_id}"
  vpc_id      = data.aws_vpc.selected.id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Allow MySQL traffic within the security group (inter-node communication)
resource "aws_vpc_security_group_ingress_rule" "mysql_internal" {
  security_group_id            = aws_security_group.percona.id
  description                  = "MySQL traffic between Percona cluster nodes (replication and Orchestrator discovery)"
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.percona.id

  tags = local.common_tags
}

# Allow MySQL traffic from specified security groups
resource "aws_vpc_security_group_ingress_rule" "mysql_client_sg" {
  for_each = toset(var.client_security_group_ids)

  security_group_id            = aws_security_group.percona.id
  description                  = "MySQL traffic from client security group"
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  referenced_security_group_id = each.value

  tags = local.common_tags
}

# Allow MySQL traffic from specified CIDRs
resource "aws_vpc_security_group_ingress_rule" "mysql_client_cidr" {
  for_each = toset(var.client_cidrs)

  security_group_id = aws_security_group.percona.id
  description       = "MySQL traffic from client CIDR"
  from_port         = 3306
  to_port           = 3306
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value

  tags = local.common_tags
}

# Fallback: Allow MySQL traffic from VPC CIDR if no client SGs or CIDRs specified
resource "aws_vpc_security_group_ingress_rule" "mysql_vpc" {
  count = length(var.client_security_group_ids) == 0 && length(var.client_cidrs) == 0 ? 1 : 0

  security_group_id = aws_security_group.percona.id
  description       = "MySQL traffic from VPC (default when no clients specified)"
  from_port         = 3306
  to_port           = 3306
  ip_protocol       = "tcp"
  cidr_ipv4         = data.aws_vpc.selected.cidr_block

  tags = local.common_tags
}

# Allow Orchestrator Raft traffic within the security group
resource "aws_vpc_security_group_ingress_rule" "orchestrator_raft" {
  security_group_id            = aws_security_group.percona.id
  description                  = "Orchestrator Raft consensus (port 10008) for leader election and topology management"
  from_port                    = 10008
  to_port                      = 10008
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.percona.id

  tags = local.common_tags
}

# Allow Orchestrator HTTP traffic within the security group
resource "aws_vpc_security_group_ingress_rule" "orchestrator_http" {
  security_group_id            = aws_security_group.percona.id
  description                  = "Orchestrator HTTP API (port 3000) for cluster management and failover coordination"
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.percona.id

  tags = local.common_tags
}

# Allow ICMP within VPC for troubleshooting
resource "aws_vpc_security_group_ingress_rule" "icmp" {
  security_group_id = aws_security_group.percona.id
  description       = "ICMP from VPC for network troubleshooting (ping, traceroute)"
  from_port         = -1
  to_port           = -1
  ip_protocol       = "icmp"
  cidr_ipv4         = data.aws_vpc.selected.cidr_block

  tags = local.common_tags
}

# Allow all outbound traffic
resource "aws_vpc_security_group_egress_rule" "all_outbound" {
  security_group_id = aws_security_group.percona.id
  description       = "Allow all outbound traffic"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = local.common_tags
}
