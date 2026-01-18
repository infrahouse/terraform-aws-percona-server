# Launch template for Percona instances
resource "aws_launch_template" "percona" {
  name_prefix   = "${local.name_prefix}-"
  image_id      = local.ami_id
  instance_type = var.instance_type

  iam_instance_profile {
    name = module.instance_profile.instance_profile_name
  }

  vpc_security_group_ids = [aws_security_group.percona.id]

  block_device_mappings {
    device_name = data.aws_ami.selected.root_device_name

    ebs {
      volume_size           = local.root_volume_size
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "enabled"
  }

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"

    tags = merge(
      local.common_tags,
      local.instance_tags,
      {
        Name = "${local.name_prefix}-instance"
      }
    )
  }

  tag_specifications {
    resource_type = "volume"

    tags = merge(
      local.common_tags,
      {
        Name = "${local.name_prefix}-volume"
      }
    )
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-lt"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "percona" {
  name_prefix         = "${local.name_prefix}-"
  desired_capacity    = var.instance_count
  min_size            = var.instance_count
  max_size            = var.instance_count
  vpc_zone_identifier = var.subnet_ids

  # Use EC2 health checks - custom daemon will set instance health
  # via autoscaling:SetInstanceHealth after rigorous validation.
  # ELB health checks are too aggressive and can terminate instances
  # with data due to transient network issues or load spikes.
  health_check_type         = "EC2"
  health_check_grace_period = 300

  # Attach to the read target group by default
  # Master registration is handled by Puppet during bootstrap
  target_group_arns = [aws_lb_target_group.read.arn]

  launch_template {
    id      = aws_launch_template.percona.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 100
      max_healthy_percentage = 101 # Launch one replacement before terminating old
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-instance"
    propagate_at_launch = true
  }

  tag {
    key                 = "module_version"
    value               = local.module_version
    propagate_at_launch = false
  }

  dynamic "tag" {
    for_each = local.common_tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  dynamic "tag" {
    for_each = local.instance_tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    create_before_destroy = true
    ignore_changes = [
      # Ignore changes to desired_capacity as it may be modified by scaling policies
      desired_capacity,
    ]
  }

  depends_on = [
    module.instance_profile,
  ]
}
