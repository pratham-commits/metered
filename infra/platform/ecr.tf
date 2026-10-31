locals {
  services = ["rider", "driver", "ride-request", "matching", "dispatch", "trip-tracking", "demand-sink"]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.services)
  name     = "rideshare/${each.key}"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep last 10"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "apps" {
  name              = "/rideshare/apps"
  retention_in_days = 14
}
