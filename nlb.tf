# Network Load Balancer for Percona cluster
resource "aws_lb" "percona" {
  name_prefix        = "prc-"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.subnet_ids

  enable_deletion_protection = false

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-nlb"
    }
  )
}

# Write target group (master only)
resource "aws_lb_target_group" "write" {
  name_prefix = "write-"
  port        = 3306
  protocol    = "TCP"
  vpc_id      = data.aws_vpc.selected.id
  target_type = "instance"

  # Faster failover: default is 300s, but for database master failover
  # we want quick removal of failed masters from the load balancer
  deregistration_delay = 30

  health_check {
    enabled             = true
    protocol            = "TCP"
    port                = "3306"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 10
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-write-tg"
      role = "write"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Read target group (replicas)
resource "aws_lb_target_group" "read" {
  name_prefix = "read-"
  port        = 3306
  protocol    = "TCP"
  vpc_id      = data.aws_vpc.selected.id
  target_type = "instance"

  # Faster failover: default is 300s, but for database replicas
  # we want quick removal of failed instances from the load balancer
  deregistration_delay = 30

  health_check {
    enabled             = true
    protocol            = "TCP"
    port                = "3306"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 10
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-read-tg"
      role = "read"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Write listener (port 3306)
resource "aws_lb_listener" "write" {
  load_balancer_arn = aws_lb.percona.arn
  port              = 3306
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.write.arn
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-write-listener"
    }
  )
}

# Read listener (port 3307 for read replicas)
resource "aws_lb_listener" "read" {
  load_balancer_arn = aws_lb.percona.arn
  port              = 3307
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.read.arn
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-read-listener"
    }
  )
}
