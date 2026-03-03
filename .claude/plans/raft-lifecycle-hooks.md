# Plan: Raft Peer Reconciliation via ASG Lifecycle Hooks

## Context

When ASG replaces instances, old nodes linger in the Orchestrator Raft peer list
because they were never explicitly removed. New nodes replay stale Raft log entries
and adopt dead peer addresses. This was discovered during S2 (Master Failover) testing.

**Solution:** Two ASG lifecycle hooks trigger a Lambda function that calls
`OrchestratorRaftCluster.add_peer()` / `remove_peer()` via SSM before the instance
fully launches or terminates.

## Design

### Lambda Function

**Source:** `lambda/raft_lifecycle/main.py`

```python
def lambda_handler(event, context):
    # Parse ASG lifecycle event from EventBridge
    detail = event["detail"]
    asg_name = detail["AutoScalingGroupName"]
    instance_id = detail["EC2InstanceId"]
    transition = detail["LifecycleTransition"]
    hook_name = detail["LifecycleHookName"]
    token = detail["LifecycleActionToken"]

    cluster = OrchestratorRaftCluster(asg_name=asg_name, region=region)

    if transition == "autoscaling:EC2_INSTANCE_LAUNCHING":
        # Get private IP of the new instance
        # Add it to Raft before Orchestrator starts on the new node
        cluster.add_peer(new_node)
    elif transition == "autoscaling:EC2_INSTANCE_TERMINATING":
        # Remove dying instance from Raft before it disappears
        cluster.remove_peer(dying_node)

    # Complete the lifecycle action so ASG can proceed
    autoscaling.complete_lifecycle_action(...)
```

**Dependencies:** `infrahouse-core` (provides `OrchestratorRaftCluster`)

**Runtime:** Python 3.12, arm64

### Event Flow

```
ASG lifecycle event
  → EventBridge rule (matches ASG name + lifecycle transitions)
    → Lambda function
      → OrchestratorRaftCluster (uses SSM to talk to Orchestrator nodes)
        → raft-add-peer / raft-remove-peer on the Raft leader
      → CompleteLifecycleAction
```

### Lifecycle Hooks

Two hooks on `aws_autoscaling_group.percona`:

1. **`raft-launch`** — `autoscaling:EC2_INSTANCE_LAUNCHING`
   - Heartbeat timeout: 300s (Lambda must complete within this)
   - Default result: `ABANDON` (if Lambda fails, don't launch a broken node)

2. **`raft-terminate`** — `autoscaling:EC2_INSTANCE_TERMINATING`
   - Heartbeat timeout: 300s
   - Default result: `CONTINUE` (if Lambda fails, terminate anyway — node is dying)

### IAM Permissions for Lambda

The Lambda execution role needs:

```
ssm:SendCommand          — on cluster instances (by cluster_id tag)
ssm:GetCommandInvocation — on * (no resource-level support)
ec2:DescribeInstances     — on * (no resource-level support)
ec2:DescribeTags          — on * (no resource-level support)
autoscaling:CompleteLifecycleAction — on the ASG
autoscaling:DescribeAutoScalingGroups — on *
```

### Security Group

The Lambda uses SSM (not direct HTTP to port 3000), so it does NOT need to be in
the Percona security group. It only needs outbound internet access to reach the SSM
API endpoint (via NAT gateway).

Create a dedicated security group for the Lambda:
- No ingress rules needed
- Egress: allow all outbound (for SSM API via NAT)

### Networking

Lambda runs in the VPC using `var.subnet_ids` (same subnets as Percona instances).
These subnets have NAT gateway access, which the Lambda needs to reach the SSM API.

## Files to Create

### 1. `lambda/raft_lifecycle/main.py`

Lambda handler:
- Parse EventBridge lifecycle event
- Instantiate `OrchestratorRaftCluster(asg_name=..., region=...)`
- On launch: `cluster.add_peer(node)` for the new instance
- On terminate: `cluster.remove_peer(node)` for the dying instance
- Call `complete_lifecycle_action()` on success
- Log all actions for CloudWatch troubleshooting

### 2. `lambda/raft_lifecycle/requirements.txt`

```
infrahouse-core
```

### 3. `lifecycle.tf`

All lifecycle hook infrastructure:

- **`module "raft_lifecycle"`** — using `infrahouse/lambda-monitored/aws`
  - `function_name = "${local.name_prefix}-raft-lifecycle"`
  - `lambda_source_dir = "${path.module}/lambda/raft_lifecycle"`
  - `lambda_subnet_ids = var.subnet_ids`
  - `lambda_security_group_ids = [aws_security_group.raft_lambda.id]`
  - `environment_variables = { ASG_NAME, REGION }`
  - `alarm_emails = var.alarm_emails`
  - `additional_iam_policy_arns = [aws_iam_policy.raft_lifecycle.arn]`
  - `timeout = 120`
  - `tags = local.common_tags`

- **`aws_security_group.raft_lambda`** — Lambda security group
  - No ingress rules
  - Egress: all outbound

- **`aws_autoscaling_lifecycle_hook.raft_launch`**
  - `autoscaling_group_name = aws_autoscaling_group.percona.name`
  - `lifecycle_transition = "autoscaling:EC2_INSTANCE_LAUNCHING"`
  - `heartbeat_timeout = 300`
  - `default_result = "ABANDON"`

- **`aws_autoscaling_lifecycle_hook.raft_terminate`**
  - `autoscaling_group_name = aws_autoscaling_group.percona.name`
  - `lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"`
  - `heartbeat_timeout = 300`
  - `default_result = "CONTINUE"`

- **`aws_cloudwatch_event_rule.raft_lifecycle`**
  - Matches EC2 Instance-Launch and Instance-Terminate lifecycle actions
    for this specific ASG

- **`aws_cloudwatch_event_target.raft_lifecycle`**
  - Routes the EventBridge rule to the Lambda function

- **`aws_lambda_permission.eventbridge`**
  - Allows EventBridge to invoke the Lambda

- **`aws_iam_policy.raft_lifecycle`** — Lambda permissions policy
  - SSM: SendCommand (scoped to cluster_id tag), GetCommandInvocation (*)
  - EC2: DescribeInstances, DescribeTags (*)
  - ASG: CompleteLifecycleAction (scoped to ASG), DescribeAutoScalingGroups (*)

## Files to Modify

### 4. `variables.tf`

Add:
```hcl
variable "alarm_emails" {
  description = "Email addresses for Lambda monitoring alarms."
  type        = list(string)
  default     = []
}
```

### 5. `test_data/percona-server/main.tf`

Pass `alarm_emails` to the module (can use an empty list or a test email).

## Verification

1. `terraform fmt -recursive && terraform validate`
2. Deploy with `make test-keep`
3. Terminate an instance, check CloudWatch logs for the Lambda
4. Verify `curl -s http://localhost:3000/api/raft-peers` shows correct peers
5. Verify new instance joins Raft cleanly after ASG replacement