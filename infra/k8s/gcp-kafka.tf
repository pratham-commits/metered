resource "helm_release" "strimzi" {
  name             = "strimzi-kafka-operator"
  repository       = "https://strimzi.io/charts/"
  chart            = "strimzi-kafka-operator"
  # 0.45.x fabric8 client crashes on GKE 1.36+ (/version has emulationMajor).
  version          = "0.48.0"
  namespace        = "kafka"
  create_namespace = true
  timeout          = 600

  set {
    name  = "watchAnyNamespace"
    value = "true"
  }
}

# KRaft dual-role pool (ZooKeeper removed in current Strimzi examples).
resource "kubectl_manifest" "kafka_nodepool" {
  yaml_body = yamlencode({
    apiVersion = "kafka.strimzi.io/v1beta2"
    kind       = "KafkaNodePool"
    metadata = {
      name      = "dual-role"
      namespace = kubernetes_namespace.rideshare.metadata[0].name
      labels = {
        "strimzi.io/cluster" = "rideshare-kafka"
      }
    }
    spec = {
      replicas = 3
      roles    = ["controller", "broker"]
      storage = {
        type = "jbod"
        volumes = [
          {
            id            = 0
            type          = "ephemeral"
            kraftMetadata = "shared"
          }
        ]
      }
    }
  })

  depends_on = [helm_release.strimzi]
}

resource "kubectl_manifest" "kafka" {
  yaml_body = yamlencode({
    apiVersion = "kafka.strimzi.io/v1beta2"
    kind       = "Kafka"
    metadata = {
      name      = "rideshare-kafka"
      namespace = kubernetes_namespace.rideshare.metadata[0].name
      annotations = {
        "strimzi.io/node-pools" = "enabled"
        "strimzi.io/kraft"      = "enabled"
      }
    }
    spec = {
      kafka = {
        version = "4.0.0"
        listeners = [
          {
            name = "internal"
            port = 9094
            type = "internal"
            tls  = true
          },
          {
            name = "external"
            port = 9095
            type = "loadbalancer"
            tls  = true
            configuration = {
              bootstrap = {
                annotations = {
                  "networking.gke.io/load-balancer-type" = "Internal"
                }
              }
              brokers = [
                for broker in range(3) : {
                  broker = broker
                  annotations = {
                    "networking.gke.io/load-balancer-type" = "Internal"
                  }
                }
              ]
            }
          }
        ]
        # TLS listeners without an authentication block: in-cluster clients and
        # Dataproc trust the cluster CA alone. Do not add authorization.type=
        # simple without users — that would deny every producer and consumer.
        config = {
          "offsets.topic.replication.factor"         = 3
          "transaction.state.log.replication.factor" = 3
          "transaction.state.log.min.isr"            = 2
          "default.replication.factor"               = 3
          "min.insync.replicas"                      = 2
          "auto.create.topics.enable"                = false
        }
      }
      entityOperator = {
        topicOperator = {}
        userOperator  = {}
      }
    }
  })

  depends_on = [kubectl_manifest.kafka_nodepool]
}

resource "kubectl_manifest" "topic_events" {
  yaml_body = yamlencode({
    apiVersion = "kafka.strimzi.io/v1beta2"
    kind       = "KafkaTopic"
    metadata = {
      name      = "ride-events"
      namespace = kubernetes_namespace.rideshare.metadata[0].name
      labels = {
        "strimzi.io/cluster" = "rideshare-kafka"
      }
    }
    spec = {
      topicName  = "ride-events"
      partitions = 6
      replicas   = 3
      config = {
        "retention.ms" = "604800000"
      }
    }
  })

  depends_on = [kubectl_manifest.kafka]
}

resource "kubectl_manifest" "topic_results" {
  yaml_body = yamlencode({
    apiVersion = "kafka.strimzi.io/v1beta2"
    kind       = "KafkaTopic"
    metadata = {
      name      = "demand-results"
      namespace = kubernetes_namespace.rideshare.metadata[0].name
      labels = {
        "strimzi.io/cluster" = "rideshare-kafka"
      }
    }
    spec = {
      topicName  = "demand-results"
      partitions = 3
      replicas   = 3
      config = {
        "retention.ms" = "604800000"
      }
    }
  })

  depends_on = [kubectl_manifest.kafka]
}
