"""
Tests for terraform-aws-percona-server module.

These tests verify the Infrastructure components (Epic #2):
- ASG configuration
- NLB with write/read target groups
- DynamoDB table for locks and topology
- S3 bucket for backups and binlogs
"""

import json
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent

import pytest
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, TERRAFORM_ROOT_DIR


@pytest.mark.parametrize(
    "aws_provider_version", ["~> 5.62", "~> 6.0"], ids=["aws-5", "aws-6"]
)
def test_module(
    service_network,
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
):
    """
    Test the Percona Server module infrastructure components.

    This test verifies:
    - Module can be planned and applied successfully
    - ASG is created with correct configuration
    - NLB and target groups are created
    - DynamoDB table is created
    - S3 bucket is created
    """
    subnet_private_ids = service_network["subnet_private_ids"]["value"]
    internet_gateway_id = service_network["internet_gateway_id"]["value"]

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

        # Verify ASG was created
        assert "asg_name" in tf_output, "ASG name should be in outputs"
        assert tf_output["asg_name"]["value"], "ASG name should not be empty"

        # Verify NLB was created
        assert "nlb_dns_name" in tf_output, "NLB DNS name should be in outputs"
        assert tf_output["nlb_dns_name"]["value"], "NLB DNS name should not be empty"

        # Verify target groups were created
        assert (
            "write_target_group_arn" in tf_output
        ), "Write TG ARN should be in outputs"
        assert "read_target_group_arn" in tf_output, "Read TG ARN should be in outputs"

        # Verify DynamoDB table was created
        assert (
            "dynamodb_table_name" in tf_output
        ), "DynamoDB table name should be in outputs"
        assert tf_output["dynamodb_table_name"][
            "value"
        ], "DynamoDB table name should not be empty"

        # Verify S3 bucket was created
        assert "s3_bucket_name" in tf_output, "S3 bucket name should be in outputs"
        assert tf_output["s3_bucket_name"][
            "value"
        ], "S3 bucket name should not be empty"

        LOG.info("All infrastructure components verified successfully")
