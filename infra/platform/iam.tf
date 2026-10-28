# Person 1. One IRSA role per service account. Trust rideshare namespace only.
#
# rideshare-driver          SA driver          DynamoDB read/write on rideshare_driver_live
# rideshare-ride-request    SA ride-request    SQS SendMessage on the match queue
# rideshare-matching        SA matching        SQS receive/delete/visibility on the match queue
# rideshare-dispatch        SA dispatch        DynamoDB GetItem/UpdateItem on rideshare_driver_live
# rideshare-trip-tracking   SA trip-tracking   S3 PutObject on the trip bucket, DynamoDB update on drivers, query on demand
# rideshare-demand-sink     SA demand-sink     DynamoDB PutItem/Query on rideshare_demand_windows
#
# Do not use Resource "*". Rider has no AWS role.
