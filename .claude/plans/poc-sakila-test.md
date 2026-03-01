# PoC: Sakila Database Integration Test

## Goal

Verify end-to-end MySQL cluster functionality by connecting from a jumphost
(emulating an application), creating the Sakila database, and querying it
through both write and read NLB endpoints.

## Current State

| Item | Status |
|------|--------|
| Percona cluster running with GTID replication | Done |
| NLB write (3306) / read (3307) endpoints | Done |
| Security group allows VPC CIDR on 3306 | Done |
| IAM: SSM, DynamoDB, S3, EC2 tags, ELB | Done |

## What Needs to Be Done

### 1. Add jumphost fixture to the test

Add `jumphost` as a parameter to the test function. It will pull in `subzone`
and other dependencies automatically. Need to pass `--test-zone-name` to pytest
(in Makefile or CLI).

### 3. Create an application MySQL user secret in test_data

In `test_data/percona-server/`:
- Generate username/password with `random_password`
- Store in `infrahouse/secret/aws` secret
- Grant the jumphost instance role permission to read it via `readers`
- Output the secret name/ARN for use in the test

### 4. Wait for Puppet to finish on all 3 instances

The cloud-init module (v2.2.3) already creates `/var/run/puppet-done`
after `ih-puppet apply` completes. No changes needed to the module.

In the test, poll all 3 instances with
`execute_command("ls /var/run/puppet-done")` in a loop (with timeout)
until all return exit code 0.

### 5. Create the app user on the master via SSM

Use `infrahouse-core`'s `EC2Instance` / `ASGInstance` which implement
`execute_command()`. From the test:
- Find the master instance (query DynamoDB topology or describe ASG + tags)
- `execute_command()` to run:
  ```sql
  CREATE USER 'sakila_user'@'10.1.%' IDENTIFIED BY '<password>';
  GRANT ALL ON sakila.* TO 'sakila_user'@'10.1.%';
  FLUSH PRIVILEGES;
  ```

### 5. Install PyMySQL on the jumphost

Use `execute_command()` on the jumphost instance:
`apt-get install -y python3-pymysql`

### 6. Load Sakila schema on the master via SSM

Use `execute_command()` on the master instance to:
1. Download Sakila: `wget https://downloads.mysql.com/docs/sakila-db.tar.gz`
2. Extract and load: `mysql < sakila-schema.sql && mysql < sakila-data.sql`

### 7. Query Sakila from the jumphost

Use `execute_command()` on the jumphost to run a Python script that:
1. Reads the app user password from Secrets Manager
2. Connects to NLB write endpoint (dns:3306)
3. `SELECT * FROM sakila.actor` — verify data exists
4. Connects to NLB read endpoint (dns:3307)
5. `SELECT * FROM sakila.actor` — verify replication works

## Proposed Test Flow

```python
def test_module():
    # Step 1: Percona cluster (existing)
    with terraform_apply(percona-server) as tf_output:
        # Step 2: Jumphost
        with terraform_apply(jumphost) as jh_output:
            # Step 3: App user secret already created by Terraform

            # Step 4: Create app user on master via SSM
            send_command_to_master(
                "mysql -e \"CREATE USER ... GRANT ALL ...\""
            )

            # Step 5-6: Run test script on jumphost
            #   - pip install pymysql
            #   - read secret from Secrets Manager
            #   - connect to NLB:3306, create sakila, load data
            #   - connect to NLB:3307, SELECT from actor
            #   - assert results match
```

## Architecture

```
                    VPC 10.1.0.0/16
 ┌──────────────────────────────────────────┐
 │  Public Subnets         Private Subnets  │
 │  ┌──────────┐          ┌──────────────┐  │
 │  │ Jumphost │          │ Percona (x3) │  │
 │  │ NLB      │          │ Master + 2R  │  │
 │  └────┬─────┘          └──────┬───────┘  │
 │       │                       │          │
 │       │    NLB (internal)     │          │
 │       │   :3306 write ────────┤          │
 │       │   :3307 read  ────────┘          │
 │       │                                  │
 │       └───── pymysql ──── NLB ───────────│
 └──────────────────────────────────────────┘
```

## No Changes Needed

- Networking: jumphost and Percona in same VPC
- Security group: already allows VPC CIDR on 3306
- NLB: already has write/read listeners
- IAM for Percona instances: SSM, DynamoDB, etc. already in place

## Open Questions

- ~~Where to create the app user~~ — ad-hoc from the test via SSM
- ~~Sakila: download tarball or embed SQL~~ — download on master via SSM
- ~~SSM helper~~ — use infrahouse-core's ASG class (we know the ASG name
  from tf_output), get instances via its property, call `execute_command()`