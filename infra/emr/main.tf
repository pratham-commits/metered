variable "flink_jar_key" {
  type    = string
  default = "flink/demand-analytics.jar"
}

resource "aws_iam_role" "emr_service" {
  name = "rideshare-emr-service"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "elasticmapreduce.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_service" {
  role       = aws_iam_role.emr_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceRole"
}

resource "aws_iam_role" "emr_ec2" {
  name = "rideshare-emr-ec2"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_ec2" {
  role       = aws_iam_role.emr_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceforEC2Role"
}

resource "aws_iam_instance_profile" "emr" {
  name = "rideshare-emr-ec2"
  role = aws_iam_role.emr_ec2.name
}

resource "aws_emr_cluster" "flink" {
  depends_on    = [aws_iam_role_policy_attachment.emr_service, aws_iam_role_policy_attachment.emr_ec2]
  name          = "rideshare-flink"
  release_label = "emr-7.14.0"
  applications  = ["Hadoop", "Flink"]
  service_role  = aws_iam_role.emr_service.arn
  log_uri       = "s3://${data.terraform_remote_state.platform.outputs.trip_bucket}/emr-logs/"

  ec2_attributes {
    subnet_id        = data.terraform_remote_state.platform.outputs.private_subnet_ids[0]
    instance_profile = aws_iam_instance_profile.emr.arn
  }

  master_instance_group {
    instance_type  = "m5.xlarge"
    instance_count = 1
  }
  core_instance_group {
    instance_type  = "m5.xlarge"
    instance_count = 1
  }

  step {
    name              = "demand-analytics"
    action_on_failure = "CONTINUE"
    hadoop_jar_step {
      jar = "command-runner.jar"
      args = [
        "bash", "-lc",
        "aws s3 cp s3://${data.terraform_remote_state.platform.outputs.trip_bucket}/${var.flink_jar_key} /tmp/demand-analytics.jar && flink run -t yarn-per-job -d /tmp/demand-analytics.jar --bootstrap '${data.terraform_remote_state.platform.outputs.kafka_bootstrap}' --input ride-events --output demand-results"
      ]
    }
  }

  configurations_json = jsonencode([
    {
      Classification = "flink-conf"
      Properties = {
        "state.backend"                    = "rocksdb"
        "execution.checkpointing.interval" = "60000"
        "state.checkpoints.dir"            = "s3://${data.terraform_remote_state.platform.outputs.trip_bucket}/flink/checkpoints/"
      }
    }
  ])

  lifecycle {
    ignore_changes = [step]
  }
}
