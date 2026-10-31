resource "aws_security_group" "msk" {
  name   = "rideshare-msk"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.this.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/rideshare/msk"
  retention_in_days = 14
}

resource "aws_msk_cluster" "this" {
  cluster_name           = "rideshare"
  kafka_version          = "3.9.x"
  number_of_broker_nodes = 3
  broker_node_group_info {
    instance_type   = "kafka.t3.small"
    client_subnets  = aws_subnet.private[*].id
    security_groups = [aws_security_group.msk.id]
    storage_info {
      ebs_storage_info { volume_size = 20 }
    }
  }
  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
  client_authentication {
    unauthenticated = true
    sasl { iam = false }
  }
  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }
}

data "aws_msk_bootstrap_brokers" "this" {
  cluster_arn = aws_msk_cluster.this.arn
}
