# Instance profile using InfraHouse module
module "instance_profile" {
  source       = "registry.infrahouse.com/infrahouse/instance-profile/aws"
  version      = "1.9.0"
  profile_name = "${local.name_prefix}-profile"
  permissions  = data.aws_iam_policy_document.percona.json
  tags         = local.common_tags
  # SSM is enabled by default
}

# Combined permissions policy document
data "aws_iam_policy_document" "percona" {
  # DynamoDB access (locks and topology)
  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.percona.arn,
    ]
  }

  # S3 access (backups and binlogs)
  statement {
    sid    = "S3"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      module.backups.bucket_arn,
      "${module.backups.bucket_arn}/*",
    ]
  }

  # Auto Scaling (scale-in protection, custom health checks, instance refresh control)
  statement {
    sid    = "AutoScaling"
    effect = "Allow"
    actions = [
      "autoscaling:SetInstanceProtection",
      "autoscaling:SetInstanceHealth",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:CancelInstanceRefresh",
    ]
    resources = ["*"]
  }

  # ELB (target group registration)
  statement {
    sid    = "ELB"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:RegisterTargets",
      "elasticloadbalancing:DeregisterTargets",
      "elasticloadbalancing:DescribeTargetHealth",
    ]
    resources = [
      aws_lb_target_group.write.arn,
      aws_lb_target_group.read.arn,
    ]
  }

  # EC2 describe (for instance metadata and tag reading)
  statement {
    sid    = "EC2Describe"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }
}

# Note: Secrets Manager access for LUKS passphrase is handled by the
# infrahouse/secret/aws module via the 'readers' parameter