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
        parameters {
            booleanParam(name: 'LOAD_SAMPLE_DATA', defaultValue: false,
                description: 'Load the sample records (db-seed hook) during this staging deploy. Leave off for a clean registry.')
        }
        stages {
            stage('Promote and deploy') {
                when { allOf { branch 'staging'; not { changeRequest() } } }
                steps {
                    checkout scm
                    script {
                    def credentials = [
                        file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG'),
                        [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds'],
                        usernamePassword(credentialsId: 'oan-helm-fork-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')
                    ]
                    // The sample loader signs in as the sample staff users (alex.carter, nina.patel) with
                    // global.aweApproverUserPassword, which keycloak-init also sets as their password. The staging
                    // overlay leaves it empty, so it comes from this Jenkins Secret text, and only when sample data is asked for.
                    if (params.LOAD_SAMPLE_DATA) {
                        credentials << string(credentialsId: 'staging-sample-users-password', variable: 'SAMPLE_USERS_PASSWORD')
                    }
                    withCredentials(credentials) {
                        sh '''
                          set -eu
                          sample=''
                          if [ "${LOAD_SAMPLE_DATA:-false}" = true ]; then
                            if [ -z "${SAMPLE_USERS_PASSWORD:-}" ]; then
                              echo 'LOAD_SAMPLE_DATA needs the Jenkins credential staging-sample-users-password' >&2
                              exit 1
                            fi
                            # A private values file, so the password is never on a command line or in the log.
                            sample_values=$(umask 077 && mktemp)
                            trap 'rm -f "$sample_values"' EXIT
                            python3 -c 'import json, os, sys; json.dump({"global": {"aweApproverUserPassword": os.environ["SAMPLE_USERS_PASSWORD"]}}, open(sys.argv[1], "w"))' "$sample_values"
                            sample="--set registry.dbSeed.loadSampleData=true -f $sample_values"
                          fi
                          rm -rf .oan-helm
                          git clone --quiet --depth 1 --filter=blob:none --sparse \\
                            https://github.com/Centre-for-Open-Societal-Systems/oan-helm.git .oan-helm
                          git -C .oan-helm sparse-checkout set scripts/ci environments/staging/values
                          bash .oan-helm/scripts/ci/deliver_staging.sh openg2p-livestock-registry livestock-registry live livestock.yaml $sample
                        '''
                    }
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
        post {
            failure {
            script {
                // Mail the DevOps list and the commit author; a controller without SMTP must not hide the failure.
                try {
                    def author = ''
                    try { author = sh(script: "git log -1 --pretty=format:'%ae'", returnStdout: true).trim() } catch (ignored) { author = '' }
                    def recipients = ['simretyibeltal@gmail.com', 'pavanns.ns@gmail.com']
                    if (author && !author.contains('noreply')) { recipients = [author] + recipients }
                    mail(
                        to: recipients.unique().join(', '),
                        subject: "Build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                        body: "Livestock Registry staging build or deploy failed.\n\nJob:     ${env.JOB_NAME}\nBranch:  ${env.BRANCH_NAME}\nBuild:   #${env.BUILD_NUMBER}\nURL:     ${env.BUILD_URL}\nConsole: ${env.BUILD_URL}console\n\nJenkins"
                    )
                } catch (err) {
                    echo "notification not sent: ${err.message}"
                }
            }
        }
        }
    }
}
return this
