# Raft peer management via ASG lifecycle hooks.
#
# Terminate hook: compares Raft peers against live ASG, removes stale ones.
# Launch hook: logs only — new instance joins Raft after Puppet bootstrap
#              (raft-join.sh in post_runcmd completes the lifecycle hook).

# Lambda function for Raft lifecycle management
module "raft_lifecycle" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.0.4"

  function_name     = "${local.name_prefix}-raft-lifecycle"
  lambda_source_dir = "${path.module}/lambda/raft_lifecycle"
  python_version    = "python3.12"
  architecture      = "arm64"
  timeout           = 120
  memory_size       = 512
  alarm_emails      = var.alarm_emails

  lambda_subnet_ids          = var.subnet_ids
  lambda_security_group_ids  = [aws_security_group.raft_lambda.id]
  additional_iam_policy_arns = [aws_iam_policy.raft_lifecycle.arn]

  environment_variables = {
    ASG_NAME = aws_autoscaling_group.percona.name
    REGION   = data.aws_region.current.name
  }

  tags = local.common_tags
}

# Security group for the Lambda function.
# Lambda uses SSM (not direct HTTP), so no ingress rules are needed.
resource "aws_security_group" "raft_lambda" {
  name_prefix = "${local.name_prefix}-raft-lambda-"
  description = "Security group for Raft lifecycle Lambda"
  vpc_id      = data.aws_vpc.selected.id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-raft-lambda-sg"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# Allow all outbound (Lambda needs to reach SSM API via NAT)
resource "aws_vpc_security_group_egress_rule" "raft_lambda_egress" {
  security_group_id = aws_security_group.raft_lambda.id
  description       = "Allow all outbound traffic for SSM API access"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"

  tags = local.common_tags
}

# ASG lifecycle hook: instance launching
# Launch hook just logs and CONTINUEs — the new instance joins Raft
# on its own after Puppet bootstraps Orchestrator.
resource "aws_autoscaling_lifecycle_hook" "raft_launch" {
  name                   = "raft-launch"
  autoscaling_group_name = aws_autoscaling_group.percona.name
  lifecycle_transition   = "autoscaling:EC2_INSTANCE_LAUNCHING"
  heartbeat_timeout      = 3600
  default_result         = "ABANDON"
}

# ASG lifecycle hook: instance terminating
resource "aws_autoscaling_lifecycle_hook" "raft_terminate" {
  name                   = "raft-terminate"
  autoscaling_group_name = aws_autoscaling_group.percona.name
  lifecycle_transition   = "autoscaling:EC2_INSTANCE_TERMINATING"
  heartbeat_timeout      = 300
  default_result         = "CONTINUE"
}

# EventBridge rule matching lifecycle events for this ASG
resource "aws_cloudwatch_event_rule" "raft_lifecycle" {
  name        = "${local.name_prefix}-raft-lifecycle"
  description = "Capture ASG lifecycle events for Raft peer management"

  event_pattern = jsonencode({
    source      = ["aws.autoscaling"]
    detail-type = ["EC2 Instance-launch Lifecycle Action", "EC2 Instance-terminate Lifecycle Action"]
    detail = {
      AutoScalingGroupName = [aws_autoscaling_group.percona.name]
    }
  })

  tags = local.common_tags
}

# Route EventBridge events to the Lambda function
resource "aws_cloudwatch_event_target" "raft_lifecycle" {
  rule = aws_cloudwatch_event_rule.raft_lifecycle.name
  arn  = module.raft_lifecycle.lambda_function_arn
}

# Allow EventBridge to invoke the Lambda
resource "aws_lambda_permission" "raft_lifecycle_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.raft_lifecycle.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.raft_lifecycle.arn
}

# --- IAM ---

# IAM policy for the Lambda execution role
# checkov:skip=CKV_AWS_356:Describe/Get actions do not support resource-level permissions
resource "aws_iam_policy" "raft_lifecycle" {
  name   = "${local.name_prefix}-raft-lifecycle"
  policy = data.aws_iam_policy_document.raft_lifecycle.json

  tags = local.common_tags
}

# checkov:skip=CKV_AWS_356:Describe/Get actions do not support resource-level permissions
data "aws_iam_policy_document" "raft_lifecycle" {
  # SSM: Send commands to cluster instances (scoped by cluster_id tag)
  statement {
    sid    = "SSMSendCommand"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
    ]
    resources = [
      "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/cluster_id"
      values   = [var.cluster_id]
    }
  }

  statement {
    sid    = "SSMSendCommandDocument"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
    ]
    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}::document/AWS-RunShellScript",
    ]
  }

  # SSM: GetCommandInvocation does not support resource-level permissions
  statement {
    sid    = "SSMGetCommandInvocation"
    effect = "Allow"
    actions = [
      "ssm:GetCommandInvocation",
    ]
    resources = ["*"]
  }

  # EC2: Describe instances and tags (not restrictable)
  statement {
    sid    = "EC2Describe"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }

  # ASG: Complete lifecycle actions (scoped to this ASG)
  statement {
    sid    = "AutoScalingLifecycle"
    effect = "Allow"
    actions = [
      "autoscaling:CompleteLifecycleAction",
    ]
    resources = [aws_autoscaling_group.percona.arn]
  }

  # ASG: Describe (not restrictable)
  statement {
    sid    = "AutoScalingDescribe"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
    ]
    resources = ["*"]
  }
}
