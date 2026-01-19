#!/usr/bin/env python3
"""
Generate architecture diagram for terraform-aws-percona-server module.

This diagram shows the AWS infrastructure for a highly available
Percona Server (MySQL) cluster with automated replication.

Requirements:
    pip install diagrams

Usage:
    python architecture.py

Output:
    architecture.png (in current directory)
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2, AutoScaling
from diagrams.aws.network import NLB, VPC
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.security import SecretsManager, IAM
from diagrams.aws.management import SystemsManager
from diagrams.aws.general import Client
from diagrams.onprem.database import MySQL

fontsize = "16"

# Match MkDocs Material theme fonts (Roboto)
graph_attr = {
    "splines": "spline",
    "nodesep": "1.5",
    "ranksep": "1.5",
    "fontsize": fontsize,
    "fontname": "Roboto",
    "dpi": "200",
}

node_attr = {
    "fontname": "Roboto",
    "fontsize": fontsize,
}

edge_attr = {
    "fontname": "Roboto",
    "fontsize": fontsize,
}

with Diagram(
    "Percona Server Cluster - AWS Architecture",
    filename="architecture",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
    outformat="png",
):
    # External clients
    app = Client("\nApplication")

    with Cluster("AWS Account"):
        # Secrets Manager
        with Cluster("Secrets Manager"):
            mysql_creds = SecretsManager("\nMySQL\nCredentials")

        with Cluster("VPC"):
            # Network Load Balancer
            with Cluster("Network Load Balancer"):
                nlb = NLB("\nInternal NLB")
                write_tg = NLB("\nWrite TG\n:3306")
                read_tg = NLB("\nRead TG\n:3307")

            # Auto Scaling Group with Percona instances
            with Cluster("Auto Scaling Group"):
                with Cluster("Percona Cluster (GTID Replication)"):
                    master = EC2("\nMaster\n(Read/Write)")
                    replica1 = EC2("\nReplica 1\n(Read Only)")
                    replica2 = EC2("\nReplica 2\n(Read Only)")

        # DynamoDB for coordination
        dynamodb = Dynamodb("\nDynamoDB\nLocks & Topology")

        # S3 for backups
        s3 = S3("\nS3 Bucket\nBackups & Binlogs")

        # IAM and SSM
        iam = IAM("\nInstance\nProfile")
        ssm = SystemsManager("\nSSM\n(Management)")

    # ============ CONNECTIONS ============

    # Client connections through NLB
    app >> Edge(label="MySQL") >> nlb
    nlb >> write_tg
    nlb >> read_tg

    # Write traffic to master only
    write_tg >> Edge(label=":3306", color="green") >> master

    # Read traffic to all replicas
    read_tg >> Edge(label=":3307", color="blue") >> replica1
    read_tg >> Edge(label=":3307", color="blue") >> replica2

    # GTID Replication
    master >> Edge(label="GTID\nReplication", style="dashed", color="orange") >> replica1
    master >> Edge(label="GTID\nReplication", style="dashed", color="orange") >> replica2

    # DynamoDB for coordination
    master >> Edge(style="dotted") >> dynamodb
    replica1 >> Edge(style="dotted") >> dynamodb
    replica2 >> Edge(style="dotted") >> dynamodb

    # Backups to S3
    master >> Edge(label="Backups", style="dashed") >> s3

    # Secrets access
    mysql_creds >> Edge(style="dotted") >> master
    mysql_creds >> Edge(style="dotted") >> replica1

    # SSM management
    ssm >> Edge(style="dotted", color="gray") >> master
    ssm >> Edge(style="dotted", color="gray") >> replica1
    ssm >> Edge(style="dotted", color="gray") >> replica2