"""
Tests for terraform-aws-percona-server module.

These tests verify:
- Infrastructure components (ASG, NLB, DynamoDB, S3)
- Percona Server bootstrap with GTID replication (Epic #3)
- End-to-end MySQL connectivity through NLB write/read endpoints
"""

import json
import time
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent

import pytest
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, TERRAFORM_ROOT_DIR

PUPPET_DONE_TIMEOUT = 900  # 15 minutes for Puppet to finish
PUPPET_POLL_INTERVAL = 30
REPLICATION_WAIT = 10  # seconds to wait for replication to catch up


def wait_for_puppet(asg: ASG, wait_timeout: int = PUPPET_DONE_TIMEOUT):
    """Wait for Puppet to finish on all instances in the ASG.

    Polls each instance for /var/run/puppet-done marker file.

    :param asg: ASG object with instances to wait on.
    :param wait_timeout: Maximum seconds to wait.
    :raises TimeoutError: if puppet doesn't finish in time.
    """
    instances = asg.instances
    pending = {inst.instance_id for inst in instances}
    LOG.info(
        "Waiting for Puppet to finish on %d instances: %s",
        len(pending),
        pending,
    )

    with timeout(wait_timeout):
        while pending:
            for instance in instances:
                if instance.instance_id not in pending:
                    continue
                try:
                    exit_code, _, _ = instance.execute_command(
                        "ls /var/run/puppet-done"
                    )
                    if exit_code == 0:
                        LOG.info("Puppet finished on %s", instance.instance_id)
                        pending.discard(instance.instance_id)
                except Exception as exc:
                    LOG.debug(
                        "Instance %s not ready yet: %s",
                        instance.instance_id,
                        exc,
                    )
            if pending:
                LOG.info(
                    "Still waiting for Puppet on %d instances: %s",
                    len(pending),
                    pending,
                )
                time.sleep(PUPPET_POLL_INTERVAL)

    LOG.info("Puppet finished on all instances")


def find_master(asg: ASG) -> ASGInstance:
    """Find the master instance by checking mysql_role tag.

    :param asg: ASG object.
    :return: Instance ID of the master.
    :raises RuntimeError: if no master found.
    """
    for instance in asg.instances:
        tags = instance.tags
        if tags.get("mysql_role") == "master":
            LOG.info(
                "Found master: %s (%s)",
                instance.instance_id,
                instance.private_ip,
            )
            return instance
    raise RuntimeError("No master instance found in ASG")


@pytest.mark.parametrize(
    "aws_provider_version", ["~> 5.62", "~> 6.0"], ids=["aws-5", "aws-6"]
)
def test_module(
    service_network,
    jumphost,
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
):
    """
    Test the Percona Server module end-to-end.

    This test verifies:
    - Module can be planned and applied successfully
    - ASG, NLB, DynamoDB table, and S3 bucket are created
    - Puppet finishes on all instances
    - Master election and GTID replication work
    - Application can connect via NLB write and read endpoints
    """
    subnet_private_ids = service_network["subnet_private_ids"]["value"]

    terraform_module_dir = osp.join(TERRAFORM_ROOT_DIR, "percona-server")

    # Clean up state files to ensure fresh terraform init
    state_files = [
        osp.join(terraform_module_dir, ".terraform"),
        osp.join(terraform_module_dir, ".terraform.lock.hcl"),
    ]
    for state_file in state_files:
        try:
            if osp.isdir(state_file):
                rmtree(state_file)
            elif osp.isfile(state_file):
                remove(state_file)
        except FileNotFoundError:
            pass

    # Generate terraform.tf with specified AWS provider version
    with open(osp.join(terraform_module_dir, "terraform.tf"), "w") as fp:
        fp.write(
            dedent(
                f"""
                terraform {{
                  required_version = "~> 1.5"
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                    random = {{
                      source  = "hashicorp/random"
                      version = "~> 3.6"
                    }}
                  }}
                }}
                """
            )
        )

    # Generate terraform.tfvars
    with open(osp.join(terraform_module_dir, "terraform.tfvars"), "w") as fp:
        fp.write(
            dedent(
                f"""
                region              = "{aws_region}"
                subnet_ids          = {json.dumps(subnet_private_ids)}
                """
            )
        )
        if test_role_arn:
            fp.write(
                dedent(
                    f"""
                role_arn = "{test_role_arn}"
                """
                )
            )

    with terraform_apply(
        terraform_module_dir,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        LOG.info("Terraform output: %s", json.dumps(tf_output, indent=4))

        # Verify infrastructure outputs
        assert tf_output["asg_name"]["value"], "ASG name should not be empty"
        assert tf_output["nlb_dns_name"]["value"], "NLB DNS should not be empty"
        assert tf_output["write_target_group_arn"]["value"]
        assert tf_output["read_target_group_arn"]["value"]
        assert tf_output["dynamodb_table_name"]["value"]
        assert tf_output["s3_bucket_name"]["value"]

        asg_name = tf_output["asg_name"]["value"]
        nlb_dns = tf_output["nlb_dns_name"]["value"]
        app_user = tf_output["app_user_name"]["value"]
        app_password = tf_output["app_user_password"]["value"]

        # Create ASG objects
        percona_asg = ASG(asg_name, region=aws_region, role_arn=test_role_arn)
        jumphost_asg_name = jumphost["jumphost_asg_name"]["value"]
        jumphost_asg = ASG(jumphost_asg_name, region=aws_region, role_arn=test_role_arn)
        jumphost_instance = jumphost_asg.instances[0]

        LOG.info("Waiting for Puppet to finish on all Percona instances...")
        wait_for_puppet(percona_asg)

        # Find the master instance
        master = find_master(percona_asg)

        # Create application MySQL user on master
        LOG.info("Creating application user '%s' on master...", app_user)
        exit_code, cout, cerr = master.execute_command(
            f'sudo mysql -u root -e "'
            f"CREATE USER '{app_user}'@'%' IDENTIFIED BY '{app_password}';"
            f"GRANT ALL ON sakila.* TO '{app_user}'@'%';"
            f"FLUSH PRIVILEGES;"
            f'"'
        )
        assert (
            exit_code == 0
        ), f"Failed to create app user: stdout={cout}, stderr={cerr}"

        # Download and load Sakila database on master
        LOG.info("Loading Sakila database on master...")
        exit_code, cout, cerr = master.execute_command(
            "cd /tmp && "
            "wget -q https://downloads.mysql.com/docs/sakila-db.tar.gz && "
            "tar xzf sakila-db.tar.gz && "
            "sudo mysql -u root < sakila-db/sakila-schema.sql && "
            "sudo mysql -u root < sakila-db/sakila-data.sql",
            execution_timeout=120,
        )
        assert exit_code == 0, f"Failed to load Sakila: stdout={cout}, stderr={cerr}"

        # Wait for replication to catch up
        LOG.info(
            "Waiting %d seconds for replication to propagate...",
            REPLICATION_WAIT,
        )
        time.sleep(REPLICATION_WAIT)

        # Install pymysql on jumphost
        LOG.info("Installing python3-pymysql on jumphost...")
        exit_code, cout, cerr = jumphost_instance.execute_command(
            "sudo apt-get install -y python3-pymysql",
            execution_timeout=120,
        )
        assert (
            exit_code == 0
        ), f"Failed to install pymysql: stdout={cout}, stderr={cerr}"

        # Query via NLB write endpoint (port 3306) from jumphost
        LOG.info("Querying Sakila via NLB write endpoint...")
        query_script = dedent(
            f"""\
            python3 -c "
            import pymysql
            conn = pymysql.connect(
                host='{nlb_dns}',
                port=3306,
                user='{app_user}',
                password='{app_password}',
                database='sakila',
            )
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM actor')
            count = cur.fetchone()[0]
            print(f'WRITE_ACTOR_COUNT={{count}}')
            assert count > 0, 'actor table should have rows'
            conn.close()
            "
            """
        )
        exit_code, cout, cerr = jumphost_instance.execute_command(
            query_script, execution_timeout=30
        )
        LOG.info("Write endpoint query: stdout=%s, stderr=%s", cout, cerr)
        assert (
            exit_code == 0
        ), f"Write endpoint query failed: stdout={cout}, stderr={cerr}"
        assert "WRITE_ACTOR_COUNT=" in cout

        # Query via NLB read endpoint (port 3307) from jumphost
        LOG.info("Querying Sakila via NLB read endpoint...")
        query_script = dedent(
            f"""\
            python3 -c "
            import pymysql
            conn = pymysql.connect(
                host='{nlb_dns}',
                port=3307,
                user='{app_user}',
                password='{app_password}',
                database='sakila',
            )
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM actor')
            count = cur.fetchone()[0]
            print(f'READ_ACTOR_COUNT={{count}}')
            assert count > 0, 'actor table should have rows (replication)'
            conn.close()
            "
            """
        )
        exit_code, cout, cerr = jumphost_instance.execute_command(
            query_script, execution_timeout=30
        )
        LOG.info("Read endpoint query: stdout=%s, stderr=%s", cout, cerr)
        assert (
            exit_code == 0
        ), f"Read endpoint query failed: stdout={cout}, stderr={cerr}"
        assert "READ_ACTOR_COUNT=" in cout

        LOG.info("All end-to-end verifications passed")
