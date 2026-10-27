// Branch and environment gates remain in the shared registry pipeline.
def call() {
    def delivery = load("ci/pipelines/dev.groovy")
    delivery.call()
}
return this
