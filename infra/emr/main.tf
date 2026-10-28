# Person 1, job owned by Person 3. Letter e.
#
# Variable flink_jar_key default flink/demand-analytics.jar.
# EMR service role and EC2 instance profile with the AWS managed EMR policies.
# Cluster rideshare-flink, release emr-7.14.0, application Flink, one m5.xlarge master,
# one m5.xlarge core, logs under s3://<trip_bucket>/emr-logs/.
# Step runs: flink run -m yarn-cluster -d s3://<bucket>/<jar> --bootstrap <tls brokers>
# --input ride-events --output demand-results.
# flink-conf: state.backend rocksdb, checkpoint interval 60000,
# checkpoints dir s3://<bucket>/flink/checkpoints/.
# lifecycle ignore_changes on the step.
