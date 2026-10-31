locals {
  irsa = {
    driver = {
      sa = "driver"
      actions = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:UpdateItem", "dynamodb:Query"]
      resources = [aws_dynamodb_table.drivers.arn]
    }
    ride-request = {
      sa = "ride-request"
      actions = ["sqs:SendMessage", "sqs:GetQueueUrl", "dynamodb:Query"]
      resources = [aws_sqs_queue.match.arn, aws_dynamodb_table.demand.arn]
    }
    matching = {
      sa = "matching"
      actions = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
      resources = [aws_sqs_queue.match.arn]
    }
    dispatch = {
      sa = "dispatch"
      actions = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
      resources = [aws_dynamodb_table.drivers.arn]
    }
    trip-tracking = {
      sa = "trip-tracking"
      actions = ["s3:PutObject", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:GetItem"]
      resources = [
        "${aws_s3_bucket.trips.arn}/*",
        aws_dynamodb_table.drivers.arn,
        aws_dynamodb_table.demand.arn,
      ]
    }
    demand-sink = {
      sa = "demand-sink"
      actions = ["dynamodb:PutItem", "dynamodb:Query"]
      resources = [aws_dynamodb_table.demand.arn]
    }
  }
}

resource "aws_iam_role" "service" {
  for_each = local.irsa
  name     = "rideshare-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = module.eks.oidc_provider_arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${module.eks.oidc_provider}:sub" = "system:serviceaccount:rideshare:${each.value.sa}"
          "${module.eks.oidc_provider}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "service" {
  for_each = local.irsa
  name     = "rideshare-${each.key}"
  role     = aws_iam_role.service[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = each.value.actions
      Resource = each.value.resources
    }]
  })
}
