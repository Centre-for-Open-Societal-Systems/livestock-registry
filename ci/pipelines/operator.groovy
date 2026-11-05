// Operator pipeline: the actions that destroy data, change a release outside the merge path, or need a person to choose.
// Job setup (done once by ASMIT, who is the only person who runs this job): a multibranch job whose Script Path is
// "Jenkinsfile.operator", with automatic branch and webhook triggering suppressed. Every build asks for approval by
// 'admin' before anything runs. Merges to develop and staging never reach this file: ci/pipelines/dev.groovy and
// ci/pipelines/staging.groovy have no parameters and run the default path on their own.
def call() {
    properties([parameters([
        choice(name: 'OPERATOR_ACTION', choices: ['fresh-install', 'connector-plan', 'connector-upgrade'],
            description: 'develop only. fresh-install backs up the New Dev databases, uninstalls the release, DROPS the databases and installs the pinned chart on an empty database. connector-plan prints, changing nothing, what connector-upgrade would do. connector-upgrade builds no images, archives the connector database and upgrades the connector release.')
    ])])
    if (env.CHANGE_ID || !(env.BRANCH_NAME in ['develop'])) {
        error('The operator pipeline runs only on develop, never for a pull request')
    }
    if (!params.OPERATOR_ACTION) {
        currentBuild.result = 'NOT_BUILT'
        echo 'Parameters are registered now. Start the build again with Build with Parameters.'
        return
    }
    if (!currentBuild.getBuildCauses('hudson.model.Cause$UserIdCause')) {
        currentBuild.result = 'NOT_BUILT'
        echo 'Operator actions run only when a person starts them, never from branch indexing or a webhook.'
        return
    }
    // Only ASMIT runs this job: the approval is restricted to the Jenkins 'admin' user.
    input message: "Run '${params.OPERATOR_ACTION}' on ${env.BRANCH_NAME}? fresh-install DROPS the New Dev databases.", ok: 'Run', submitter: 'admin'
    env.NEW_DEV_DELIVERY_ACTION = params.OPERATOR_ACTION
    def delivery
    node {
        checkout scm
        def environment = env.BRANCH_NAME == 'staging' ? 'staging' : 'dev'
        delivery = load("ci/pipelines/${environment}.groovy")
    }
    currentBuild.description = "Operator action: ${params.OPERATOR_ACTION}"
    delivery.call()
}
return this
