# Plan: Add credentials_secret_readers variable

## Context

The PMM module (`infrahouse/pmm-ecs/aws`) deploys a Lambda function that
reconciles ASG membership with PMM monitored services. The Lambda needs to
read the MySQL credentials secret created by the percona-server module to
connect to database instances for monitoring.

The `infrahouse/secret/aws` module applies an explicit deny resource policy,
so only principals listed in `readers` can access the secret. The
percona-server module currently hardcodes `readers` to only the instance
profile role.

## Change

Add a `credentials_secret_readers` variable so external consumers (like the
PMM reconciler Lambda) can be granted read access to the MySQL credentials
secret.

## Files to Modify

### 1. `variables.tf`

Add:

```hcl
variable "credentials_secret_readers" {
  description = <<-EOF
    Additional IAM role ARNs that can read the MySQL credentials secret.
    Use this to grant access to external services (e.g., PMM reconciler Lambda)
    that need database credentials for monitoring.
  EOF
  type    = list(string)
  default = []
}
```

### 2. `secrets.tf`

Change the `readers` argument of `module "mysql_credentials"` from:

```hcl
  readers = [
    module.instance_profile.instance_role_arn
  ]
```

to:

```hcl
  readers = concat(
    [module.instance_profile.instance_role_arn],
    var.credentials_secret_readers
  )
```

## Usage by PMM module

```hcl
module "percona_server" {
  source  = "infrahouse/percona-server/aws"
  ...
  credentials_secret_readers = [module.pmm.reconciler_lambda_role_arn]
}

module "pmm" {
  source  = "infrahouse/pmm-ecs/aws"
  ...
  monitored_asgs = [
    {
      asg_name               = module.percona_server.asg_name
      credentials_secret_arn = module.percona_server.mysql_credentials_secret_arn
      service_type           = "mysql"
      port                   = 3306
      username               = "monitor"
    }
  ]
}
```

No chicken-and-egg: PMM creates the Lambda role, percona-server adds it
to readers.

## Verification

1. `terraform fmt -check -recursive`
2. `make test-keep` (existing tests should still pass)