"""
Tests for terraform-aws-percona-server module.

These tests verify:
- Infrastructure components (ASG, NLB, DynamoDB, S3)
- Percona Server bootstrap with GTID replication (Epic #3)
- End-to-end MySQL connectivity through NLB write/read endpoints
- S2: Master failover via Orchestrator (issue #43)
"""

import json
import time
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent
from typing import List

import pytest
from infrahouse_core.aws import get_client
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, TERRAFORM_ROOT_DIR

PUPPET_DONE_TIMEOUT = 900  # 15 minutes for Puppet to finish
PUPPET_POLL_INTERVAL = 30
REPLICATION_WAIT = 10  # seconds to wait for replication to catch up
FAILOVER_TIMEOUT = 120  # seconds to wait for Orchestrator failover
ASG_REPLACEMENT_TIMEOUT = 600  # 10 minutes for ASG to replace terminated instance


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


def wait_for_new_master(
    asg: ASG,
    old_master_id: str,
    wait_timeout: int = FAILOVER_TIMEOUT,
) -> ASGInstance:
    """Wait for a new master to be elected after failover.

    Polls ASG instances for a mysql_role=master tag on an instance
    that is NOT the old master.

    :param asg: ASG object.
    :param old_master_id: Instance ID of the terminated master.
    :param wait_timeout: Maximum seconds to wait.
    :return: The new master ASGInstance.
    :raises TimeoutError: if no new master is elected in time.
    """
    LOG.info(
        "Waiting for new master (old master: %s)...",
        old_master_id,
    )
    with timeout(wait_timeout):
        while True:
            for instance in asg.instances:
                if instance.instance_id == old_master_id:
                    continue
                if instance.state != "running":
                    continue
                tags = instance.tags
                if tags.get("mysql_role") == "master":
                    LOG.info(
                        "New master elected: %s (%s)",
                        instance.instance_id,
                        instance.private_ip,
                    )
                    return instance
            LOG.info("No new master yet, waiting...")
            time.sleep(10)


def wait_for_healthy_instances(
    asg: ASG,
    count: int,
    wait_timeout: int = ASG_REPLACEMENT_TIMEOUT,
) -> List[ASGInstance]:
    """Wait for ASG to have the expected number of InService instances.

    :param asg: ASG object.
    :param count: Expected number of healthy instances.
    :param wait_timeout: Maximum seconds to wait.
    :return: List of healthy ASGInstance objects.
    :raises TimeoutError: if count not reached in time.
    """
    LOG.info(
        "Waiting for %d healthy instances in ASG...",
        count,
    )
    with timeout(wait_timeout):
        while True:
            healthy = [
                inst for inst in asg.instances if inst.lifecycle_state == "InService"
            ]
            LOG.info(
                "Healthy instances: %d/%d",
                len(healthy),
                count,
            )
            if len(healthy) >= count:
                return healthy
            time.sleep(15)


def query_nlb_endpoint(
    jumphost_instance: ASGInstance,
    nlb_dns: str,
    port: int,
    user: str,
    password: str,
    label: str,
) -> str:
    """Query MySQL via NLB endpoint from jumphost, return stdout.

    :param jumphost_instance: Jumphost ASGInstance to run the query from.
    :param nlb_dns: NLB DNS name.
    :param port: NLB listener port (3306 for write, 3307 for read).
    :param user: MySQL username.
    :param password: MySQL password.
    :param label: Label for logging (e.g. "WRITE" or "READ").
    :return: stdout from the query script.
    :raises AssertionError: if the query fails.
    """
    query_script = dedent(
        f"""\
        python3 -c "
        import pymysql
        conn = pymysql.connect(
            host='{nlb_dns}',
            port={port},
            user='{user}',
            password='{password}',
            database='sakila',
            connect_timeout=10,
            read_timeout=10,
        )
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM actor')
        count = cur.fetchone()[0]
        print(f'{label}_ACTOR_COUNT={{count}}')
        assert count > 0, 'actor table should have rows'
        conn.close()
        "
        """
    )
    exit_code, cout, cerr = jumphost_instance.execute_command(
        query_script, execution_timeout=30
    )
    LOG.info(
        "%s endpoint query: stdout=%s, stderr=%s",
        label,
        cout,
        cerr,
    )
    assert (
        exit_code == 0
    ), f"{label} endpoint query failed: stdout={cout}, stderr={cerr}"
    assert f"{label}_ACTOR_COUNT=" in cout
    return cout


def get_target_health(
    target_group_arn: str,
    region: str,
    role_arn: str,
) -> dict:
    """Get healthy target IDs for a target group.

    :param target_group_arn: ARN of the target group.
    :param region: AWS region.
    :param role_arn: IAM role to assume.
    :return: Dict mapping instance_id -> health state.
    """
    elbv2 = get_client("elbv2", region=region, role_arn=role_arn)
    response = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
    result = {}
    for target in response["TargetHealthDescriptions"]:
        instance_id = target["Target"]["Id"]
        state = target["TargetHealth"]["State"]
        result[instance_id] = state
    return result


@pytest.mark.parametrize(
    "aws_provider_version", ["~> 5.62", "~> 6.0"], ids=["aws-5", "aws-6"]
)
@pytest.mark.parametrize(
    "percona_server_version",
    [None, "8.4.7-7"],
    ids=["percona-8.0", "percona-8.4"],
)
def test_module(
    service_network,
    jumphost,
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
    percona_server_version,
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
        if percona_server_version is not None:
            fp.write(
                dedent(
                    f"""
                percona_server_version = "{percona_server_version}"
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
            f"CREATE USER IF NOT EXISTS '{app_user}'@'%' IDENTIFIED BY '{app_password}';"
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
            "wget -qN https://downloads.mysql.com/docs/sakila-db.tar.gz && "
            "tar xzf sakila-db.tar.gz && "
            "sudo mysql -u root -e 'DROP DATABASE IF EXISTS sakila' && "
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
        query_nlb_endpoint(
            jumphost_instance,
            nlb_dns,
            3306,
            app_user,
            app_password,
            "WRITE",
        )

        # Query via NLB read endpoint (port 3307) from jumphost
        LOG.info("Querying Sakila via NLB read endpoint...")
        query_nlb_endpoint(
            jumphost_instance,
            nlb_dns,
            3307,
            app_user,
            app_password,
            "READ",
        )

        LOG.info("All end-to-end verifications passed")


# @pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
# @pytest.mark.parametrize(
#     "percona_server_version",
#     [None],
#     ids=["percona-8.0"],
# )
# def test_master_failover(
#     service_network,
#     jumphost,
#     test_role_arn,
#     keep_after,
#     aws_region,
#     aws_provider_version,
#     percona_server_version,
# ):
#     """
#     S2: Master Failover (Orchestrator) - Issue #43.
#
#     Terminate the master instance. Orchestrator detects failure,
#     promotes a replica, executes post-failover hooks (NLB write TG
#     update, scale-in protection, DynamoDB topology, EC2 tags).
#     Write endpoint recovers. ASG replaces the terminated instance;
#     new instance joins as replica.
#
#     Validates:
#     - Orchestrator DeadMaster detection and automatic promotion
#     - Post-failover hooks (NLB, scale-in protection, DynamoDB, tags)
#     - ASG self-healing (replacement instance joins as replica)
#     - NLB write/read endpoint continuity
#     """
#     subnet_private_ids = service_network["subnet_private_ids"]["value"]
#     terraform_module_dir = osp.join(TERRAFORM_ROOT_DIR, "percona-server")
#
#     # Clean up state files to ensure fresh terraform init
#     state_files = [
#         osp.join(terraform_module_dir, ".terraform"),
#         osp.join(terraform_module_dir, ".terraform.lock.hcl"),
#     ]
#     for state_file in state_files:
#         try:
#             if osp.isdir(state_file):
#                 rmtree(state_file)
#             elif osp.isfile(state_file):
#                 remove(state_file)
#         except FileNotFoundError:
#             pass
#
#     # Generate terraform.tf
#     with open(osp.join(terraform_module_dir, "terraform.tf"), "w") as fp:
#         fp.write(
#             dedent(
#                 f"""
#                 terraform {{
#                   required_version = "~> 1.5"
#                   required_providers {{
#                     aws = {{
#                       source  = "hashicorp/aws"
#                       version = "{aws_provider_version}"
#                     }}
#                     random = {{
#                       source  = "hashicorp/random"
#                       version = "~> 3.6"
#                     }}
#                   }}
#                 }}
#                 """
#             )
#         )
#
#     # Generate terraform.tfvars
#     with open(osp.join(terraform_module_dir, "terraform.tfvars"), "w") as fp:
#         fp.write(
#             dedent(
#                 f"""
#                 region              = "{aws_region}"
#                 subnet_ids          = {json.dumps(subnet_private_ids)}
#                 """
#             )
#         )
#         if test_role_arn:
#             fp.write(
#                 dedent(
#                     f"""
#                 role_arn = "{test_role_arn}"
#                 """
#                 )
#             )
#         if percona_server_version is not None:
#             fp.write(
#                 dedent(
#                     f"""
#                 percona_server_version = "{percona_server_version}"
#                 """
#                 )
#             )
#
#     with terraform_apply(
#         terraform_module_dir,
#         destroy_after=not keep_after,
#         json_output=True,
#     ) as tf_output:
#         asg_name = tf_output["asg_name"]["value"]
#         nlb_dns = tf_output["nlb_dns_name"]["value"]
#         app_user = tf_output["app_user_name"]["value"]
#         app_password = tf_output["app_user_password"]["value"]
#         write_tg_arn = tf_output["write_target_group_arn"]["value"]
#
#         percona_asg = ASG(asg_name, region=aws_region, role_arn=test_role_arn)
#         jumphost_asg_name = jumphost["jumphost_asg_name"]["value"]
#         jumphost_asg = ASG(
#             jumphost_asg_name,
#             region=aws_region,
#             role_arn=test_role_arn,
#         )
#         jumphost_instance = jumphost_asg.instances[0]
#
#         # Phase 1: Wait for cluster to be ready
#         LOG.info("Phase 1: Waiting for cluster bootstrap...")
#         wait_for_puppet(percona_asg)
#         master = find_master(percona_asg)
#         old_master_id = master.instance_id
#         old_master_ip = master.private_ip
#
#         # Load Sakila and create app user for endpoint verification
#         LOG.info("Creating app user '%s' on master...", app_user)
#         exit_code, cout, cerr = master.execute_command(
#             f'sudo mysql -u root -e "'
#             f"CREATE USER IF NOT EXISTS '{app_user}'@'%'"
#             f" IDENTIFIED BY '{app_password}';"
#             f"GRANT ALL ON sakila.* TO '{app_user}'@'%';"
#             f"FLUSH PRIVILEGES;"
#             f'"'
#         )
#         assert (
#             exit_code == 0
#         ), f"Failed to create app user: stdout={cout}, stderr={cerr}"
#
#         LOG.info("Loading Sakila database on master...")
#         exit_code, cout, cerr = master.execute_command(
#             "cd /tmp && "
#             "wget -qN https://downloads.mysql.com/docs/sakila-db.tar.gz && "
#             "tar xzf sakila-db.tar.gz && "
#             "sudo mysql -u root -e 'DROP DATABASE IF EXISTS sakila' && "
#             "sudo mysql -u root < sakila-db/sakila-schema.sql && "
#             "sudo mysql -u root < sakila-db/sakila-data.sql",
#             execution_timeout=120,
#         )
#         assert exit_code == 0, f"Failed to load Sakila: stdout={cout}, stderr={cerr}"
#
#         time.sleep(REPLICATION_WAIT)
#
#         # Install pymysql on jumphost
#         LOG.info("Installing python3-pymysql on jumphost...")
#         exit_code, cout, cerr = jumphost_instance.execute_command(
#             "sudo apt-get install -y python3-pymysql",
#             execution_timeout=120,
#         )
#         assert (
#             exit_code == 0
#         ), f"Failed to install pymysql: stdout={cout}, stderr={cerr}"
#
#         # Verify pre-failover endpoints
#         LOG.info("Verifying pre-failover write endpoint...")
#         query_nlb_endpoint(
#             jumphost_instance,
#             nlb_dns,
#             3306,
#             app_user,
#             app_password,
#             "WRITE",
#         )
#         LOG.info("Verifying pre-failover read endpoint...")
#         query_nlb_endpoint(
#             jumphost_instance,
#             nlb_dns,
#             3307,
#             app_user,
#             app_password,
#             "READ",
#         )
#
#         # Record pre-failover write TG targets
#         pre_failover_write_tg = get_target_health(
#             write_tg_arn,
#             aws_region,
#             test_role_arn,
#         )
#         LOG.info(
#             "Pre-failover write TG targets: %s",
#             json.dumps(pre_failover_write_tg),
#         )
#         assert (
#             old_master_id in pre_failover_write_tg
#         ), f"Master {old_master_id} should be in write TG"
#
#         # Phase 2: Terminate master instance
#         LOG.info(
#             "Phase 2: Terminating master %s (%s)...",
#             old_master_id,
#             old_master_ip,
#         )
#         ec2 = get_client("ec2", region=aws_region, role_arn=test_role_arn)
#         ec2.terminate_instances(InstanceIds=[old_master_id])
#         LOG.info("Master instance terminated")
#
#         # Phase 3: Wait for Orchestrator failover
#         LOG.info("Phase 3: Waiting for Orchestrator failover...")
#         new_master = wait_for_new_master(percona_asg, old_master_id, FAILOVER_TIMEOUT)
#         new_master_id = new_master.instance_id
#         LOG.info(
#             "New master: %s (%s)",
#             new_master_id,
#             new_master.private_ip,
#         )
#
#         # Verify new master has mysql_role=master tag
#         assert new_master.tags.get("mysql_role") == "master"
#         assert new_master_id != old_master_id
#
#         # Phase 4: Verify post-failover hooks
#         LOG.info("Phase 4: Verifying post-failover hooks...")
#
#         # 4a: Write TG should now point to the new master
#         # NLB health checks take ~30s, so poll until the new master
#         # appears healthy in the write TG
#         LOG.info("Waiting for new master to become healthy in write TG...")
#         with timeout(120):
#             while True:
#                 write_tg = get_target_health(
#                     write_tg_arn,
#                     aws_region,
#                     test_role_arn,
#                 )
#                 LOG.info("Write TG targets: %s", json.dumps(write_tg))
#                 if write_tg.get(new_master_id) == "healthy":
#                     break
#                 time.sleep(10)
#         LOG.info("New master is healthy in write TG")
#
#         # 4b: Verify write endpoint serves traffic after failover
#         LOG.info(
#             "Verifying write endpoint after failover "
#             "(may take a moment for NLB to route)..."
#         )
#         with timeout(120):
#             while True:
#                 try:
#                     query_nlb_endpoint(
#                         jumphost_instance,
#                         nlb_dns,
#                         3306,
#                         app_user,
#                         app_password,
#                         "POST_FAILOVER_WRITE",
#                     )
#                     break
#                 except AssertionError as exc:
#                     LOG.info(
#                         "Write endpoint not ready yet: %s",
#                         exc,
#                     )
#                     time.sleep(10)
#         LOG.info("Write endpoint recovered after failover")
#
#         # 4c: Read endpoint should still work (replicas survived)
#         LOG.info("Verifying read endpoint after failover...")
#         query_nlb_endpoint(
#             jumphost_instance,
#             nlb_dns,
#             3307,
#             app_user,
#             app_password,
#             "POST_FAILOVER_READ",
#         )
#
#         # Phase 5: Wait for ASG replacement
#         LOG.info("Phase 5: Waiting for ASG to replace terminated " "instance...")
#         wait_for_healthy_instances(percona_asg, 3)
#
#         # Wait for Puppet on the replacement instance
#         LOG.info("Waiting for Puppet on replacement instance...")
#         wait_for_puppet(percona_asg)
#
#         # Phase 6: Verify final cluster state
#         LOG.info("Phase 6: Verifying final cluster state...")
#
#         # Verify we have exactly one master and two replicas
#         master_count = 0
#         replica_count = 0
#         for instance in percona_asg.instances:
#             if instance.lifecycle_state != "InService":
#                 continue
#             role = instance.tags.get("mysql_role")
#             if role == "master":
#                 master_count += 1
#             elif role == "replica":
#                 replica_count += 1
#         LOG.info(
#             "Final cluster: %d master(s), %d replica(s)",
#             master_count,
#             replica_count,
#         )
#         assert master_count == 1, f"Expected 1 master, got {master_count}"
#         assert replica_count == 2, f"Expected 2 replicas, got {replica_count}"
#
#         # Verify the replacement instance joined replication
#         # by checking the topology via orchestrator-client
#         LOG.info("Checking Orchestrator topology...")
#         exit_code, topology_out, cerr = new_master.execute_command(
#             "orchestrator-client -c topology"
#         )
#         LOG.info("Orchestrator topology:\n%s", topology_out)
#         assert exit_code == 0, f"orchestrator-client failed: stderr={cerr}"
#
#         # Verify final NLB endpoints still work
#         LOG.info("Verifying final write endpoint...")
#         query_nlb_endpoint(
#             jumphost_instance,
#             nlb_dns,
#             3306,
#             app_user,
#             app_password,
#             "FINAL_WRITE",
#         )
#         LOG.info("Verifying final read endpoint...")
#         query_nlb_endpoint(
#             jumphost_instance,
#             nlb_dns,
#             3307,
#             app_user,
#             app_password,
#             "FINAL_READ",
#         )
#
#         LOG.info("S2: Master failover test passed")
