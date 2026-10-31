resource "aws_security_group" "lambda" {
  name   = "rideshare-lambda"
  vpc_id = data.terraform_remote_state.platform.outputs.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "rds_from_lambda" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = data.terraform_remote_state.platform.outputs.db_security_group_id
  source_security_group_id = aws_security_group.lambda.id
}

resource "aws_iam_role" "lambda" {
  name = "rideshare-fare"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "rideshare-fare"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::${data.terraform_remote_state.platform.outputs.trip_bucket}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = data.terraform_remote_state.platform.outputs.db_secret_arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Query", "dynamodb:GetItem"]
        Resource = data.terraform_remote_state.platform.outputs.demand_table_arn
      }
    ]
  })
}

resource "aws_lambda_function" "estimate" {
  function_name    = "rideshare-fare-estimate"
  role             = aws_iam_role.lambda.arn
  depends_on       = [aws_iam_role_policy_attachment.lambda_vpc, aws_iam_role_policy.lambda]
  runtime          = "python3.12"
  handler          = "handler.estimate"
  filename         = "${path.module}/../../services/fare/dist/fare.zip"
  source_code_hash = filebase64sha256("${path.module}/../../services/fare/dist/fare.zip")
  timeout          = 20
  memory_size      = 256
  vpc_config {
    subnet_ids         = data.terraform_remote_state.platform.outputs.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      SECRET_ARN   = data.terraform_remote_state.platform.outputs.db_secret_arn
      DEMAND_TABLE = "rideshare_demand_windows"
    }
  }
}

resource "aws_lambda_function" "final" {
  function_name    = "rideshare-fare-final"
  role             = aws_iam_role.lambda.arn
  depends_on       = [aws_iam_role_policy_attachment.lambda_vpc, aws_iam_role_policy.lambda]
  runtime          = "python3.12"
  handler          = "handler.finalize"
  filename         = "${path.module}/../../services/fare/dist/fare.zip"
  source_code_hash = filebase64sha256("${path.module}/../../services/fare/dist/fare.zip")
  timeout          = 20
  memory_size      = 256
  vpc_config {
    subnet_ids         = data.terraform_remote_state.platform.outputs.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      SECRET_ARN   = data.terraform_remote_state.platform.outputs.db_secret_arn
      DEMAND_TABLE = "rideshare_demand_windows"
    }
  }
}

resource "aws_apigatewayv2_api" "fare" {
  name          = "rideshare-fare"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "estimate" {
  api_id                 = aws_apigatewayv2_api.fare.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.estimate.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "estimate" {
  api_id    = aws_apigatewayv2_api.fare.id
  route_key = "POST /estimate"
  target    = "integrations/${aws_apigatewayv2_integration.estimate.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.fare.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.estimate.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.fare.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.estimate.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.fare.execution_arn}/*/*"
}

resource "aws_lambda_permission" "s3" {
  statement_id  = "AllowS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.final.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${data.terraform_remote_state.platform.outputs.trip_bucket}"
}

resource "aws_s3_bucket_notification" "fare" {
  bucket = data.terraform_remote_state.platform.outputs.trip_bucket
  lambda_function {
    lambda_function_arn = aws_lambda_function.final.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "completions/"
    filter_suffix       = ".json"
  }
  depends_on = [aws_lambda_permission.s3]
}

output "fare_estimate_url" {
  value = "${aws_apigatewayv2_api.fare.api_endpoint}/estimate"
}
