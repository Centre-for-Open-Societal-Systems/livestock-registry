// The staging branch builds nothing. A merge into staging promotes the chart that develop built from this source tree
// (the same image digests, under an rc version), deploys it and publishes it. See scripts/ci/deliver_staging.sh of oan-helm.
// The build fails if develop never built this tree: staging only runs what New Dev ran first.
// The connector release follows the registry in a second stage, with the connector images of that same develop build.
def call() {
    pipeline {
        agent { label 'vpn-agent2' }
        options {
            timestamps()
            disableConcurrentBuilds()
            buildDiscarder(logRotator(numToKeepStr: '30'))
            timeout(time: 60, unit: 'MINUTES')
        }
        stages {
            stage('Promote and deploy') {
                when { allOf { branch 'staging'; not { changeRequest() } } }
                steps {
                    checkout scm
                    withCredentials([
                        file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG'),
                        [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds'],
                        usernamePassword(credentialsId: 'oan-helm-fork-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')
                    ]) {
                        sh '''
                          set -eu
                          rm -rf .oan-helm
                          git clone --quiet --depth 1 --filter=blob:none --sparse \\
                            https://github.com/Centre-for-Open-Societal-Systems/oan-helm.git .oan-helm
                          git -C .oan-helm sparse-checkout set scripts/ci environments/staging/values
                          bash .oan-helm/scripts/ci/deliver_staging.sh openg2p-livestock-registry livestock-registry live livestock.yaml
                        '''
                    }
                }
            }
            stage('Upgrade connector') {
                // After the registry is promoted and deployed: the livestock-connector release goes to the registry-connector
                // images of the same develop build, by digest. See ci/connector/upgrade-livestock-connector-staging.sh. Helm only; --atomic restores the
                // previous revision if the rollout or the definitions hook fails.
                when { allOf { branch 'staging'; not { changeRequest() } } }
                steps {
                    withCredentials([
                        file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG'),
                        [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds']
                    ]) {
                        sh 'bash ci/connector/upgrade-livestock-connector-staging.sh'
                    }
                }
            }
        }
    }
}
return this
