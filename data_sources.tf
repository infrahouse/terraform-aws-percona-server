data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# Get instance type details to detect instance store availability
data "aws_ec2_instance_type" "selected" {
  instance_type = var.instance_type
}

data "aws_subnet" "selected" {
  id = var.subnet_ids[0]
}

data "aws_vpc" "selected" {
  id = data.aws_subnet.selected.vpc_id
}

# Get latest Ubuntu Pro LTS AMI if ami_id is not specified
data "aws_ami" "ubuntu" {
  count       = var.ami_id == null ? 1 : 0
  most_recent = true

  filter {
    name   = "name"
    values = [local.ami_name_pattern]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }

  owners = ["099720109477"] # Canonical
}

# Get details of the selected AMI (either user-provided or Ubuntu default)
data "aws_ami" "selected" {
  filter {
    name   = "image-id"
    values = [local.ami_id]
  }
}
