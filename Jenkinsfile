// Livestock-registry CI/CD pipeline.

// RP_VERSION below (0.0.0-develop.296) is carried over from the original
// draft as-is

pipeline {
    agent { label 'vpn-agent2' }

    environment {
        AWS_REGION       = 'ap-south-1'
        ECR_PATH         = 'openg2p/livestock-registry'
        RP_VERSION       = '0.0.0-develop.296' // TODO verify — see header note
        HELM_RELEASE     = 'livestock-registry'
        HELM_NAMESPACE   = 'live'
       
        HELM_CHART_REPO  = 'openg2p'
        HELM_CHART_URL   = 'https://openg2p.github.io/openg2p-helm'
        HELM_CHART_REF   = 'openg2p/openg2p-farmer-registry'
        HELM_CHART_VER   = '1.2.0'

       
        HELM_NAMESPACE_DEV       = 'live'
        DEV_KUBECONFIG_CRED_ID   = 'gen2-dev-livestock-kubeconfig'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Build & Push Images') {
            steps {
                withCredentials([
                    string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID'),
                    [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-ecr-creds']
                ]) {
                    script {
                        env.ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
                        env.IMAGE_TAG    = env.GIT_COMMIT.take(12)
                    }
                    sh '''
                        echo "=== Logging in to ECR ==="
                        aws ecr get-login-password --region ${AWS_REGION} | \
                            docker login --username AWS --password-stdin ${ECR_REGISTRY}
                    '''
                    script {
                        def components = ['staff-api', 'partner-api', 'celery', 'db-seed', 'sanity-tests', 'staff-ui']
                        components.each { name ->
                            def image = "${env.ECR_REGISTRY}/${ECR_PATH}/${name}:${env.IMAGE_TAG}"
                            sh """
                                echo "=== Building and pushing ${name} ==="
                                docker build --build-arg RP_VERSION=${RP_VERSION} \
                                    -f docker/${name}/Dockerfile -t ${image} --no-cache .
                                docker push ${image}
                            """
                        }
                    }
                }
            }
        }

        stage('Prepare Deploy Values') {
          
            when { branch 'develop' }
            steps {
                sh """
                    cat > /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml <<EOF
registry:
  staffApi:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/staff-api
      tag: "${env.IMAGE_TAG}"
  partnerApi:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/partner-api
      tag: "${env.IMAGE_TAG}"
  celeryWorker:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/celery
      tag: "${env.IMAGE_TAG}"
  celeryBeat:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/celery
      tag: "${env.IMAGE_TAG}"
  dbSeed:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/db-seed
      tag: "${env.IMAGE_TAG}"
  staffUi:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/staff-ui
      tag: "${env.IMAGE_TAG}"
  sanity:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/sanity-tests
      tag: "${env.IMAGE_TAG}"
EOF
                """
            }
        }

        stage('Deploy to Development') {
 
            // `helm upgrade --install` (not `--reuse-values`) is used
            // deliberately: every run supplies the full intended value set
            // (checked-in values.yaml + these --set flags) from repo state,
            // so there's nothing to drift out of sync with and no
            // dependency on a prior release already existing -- unlike the
            // staging stage below, which targets an already-running release
            // built from a DIFFERENT chart lineage and has no in-repo
            // values file to be declarative from.        
           
            // Wrapped in catchError so a problem specific to the dev
            // cluster (still new, less battle-tested than staging) does
            // NOT block the staging "Deploy to Live" stage below from
            // running. A dev-deploy failure marks this stage (and the
            // build) unstable/failed for visibility, but doesn't abort
            // the pipeline before staging's own deploy gets a chance.
            when { branch 'develop' }
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    withCredentials([file(credentialsId: "${DEV_KUBECONFIG_CRED_ID}", variable: 'KUBECONFIG')]) {
                        sh """
                            helm repo add ${HELM_CHART_REPO} ${HELM_CHART_URL} || true
                            helm repo update ${HELM_CHART_REPO}
                            helm dependency build ./helm/openg2p-livestock-registry

                            IMAGE_SET_FLAGS="
                                --set registry.staffApi.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/staff-api
                                --set registry.staffApi.image.tag=${env.IMAGE_TAG}
                                --set registry.partnerApi.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/partner-api
                                --set registry.partnerApi.image.tag=${env.IMAGE_TAG}
                                --set registry.celeryWorker.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/celery
                                --set registry.celeryWorker.image.tag=${env.IMAGE_TAG}
                                --set registry.celeryBeat.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/celery
                                --set registry.celeryBeat.image.tag=${env.IMAGE_TAG}
                                --set registry.dbSeed.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/db-seed
                                --set registry.dbSeed.image.tag=${env.IMAGE_TAG}
                                --set registry.staffUi.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/staff-ui
                                --set registry.staffUi.image.tag=${env.IMAGE_TAG}
                                --set registry.sanity.image.repository=${env.ECR_REGISTRY}/${ECR_PATH}/sanity-tests
                                --set registry.sanity.image.tag=${env.IMAGE_TAG}
                            "

                            # Dry-run audit trail, same reasoning as staging's own dry-run step.
                            helm template \${HELM_RELEASE} ./helm/openg2p-livestock-registry -n \${HELM_NAMESPACE_DEV} \
                                \$IMAGE_SET_FLAGS \
                                > /tmp/dev-rendered-\${BUILD_NUMBER}.yaml
                            echo "Rendered \$(wc -l < /tmp/dev-rendered-\${BUILD_NUMBER}.yaml) lines from the in-repo chart's own values.yaml plus image overrides only (public hostname untouched -- see header comment). Archived for audit."

                            # No --atomic here either, same reasoning as staging: if
                            # id-generator's GitLab-403 ImagePullBackOff is present on
                            # this cluster too (same private-registry credential
                            # problem, likely cluster-agnostic — not yet independently
                            # confirmed on dev), --wait would block the full timeout
                            # and auto-rollback would discard a good deploy.
                            helm upgrade --install \${HELM_RELEASE} ./helm/openg2p-livestock-registry -n \${HELM_NAMESPACE_DEV} \
                                --create-namespace \
                                \$IMAGE_SET_FLAGS \
                                --cleanup-on-fail --timeout 10m

                            kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-api -n \${HELM_NAMESPACE_DEV} --timeout=180s
                            kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-ui -n \${HELM_NAMESPACE_DEV} --timeout=180s
                            kubectl rollout status deployment/\${HELM_RELEASE}-partner-api -n \${HELM_NAMESPACE_DEV} --timeout=180s
                        """
                        archiveArtifacts artifacts: '/tmp/dev-rendered-*.yaml', allowEmptyArchive: true
                    }
                }
            }
        }

        stage('Deploy to Live') {
            when { branch 'develop' }
            steps {
                withCredentials([file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        helm repo add ${HELM_CHART_REPO} ${HELM_CHART_URL} || true
                        helm repo update ${HELM_CHART_REPO}

                        # Dry-run + diff, kept even without a human gate so there's an
                        # audit trail to look at if a deploy ever needs investigating.
                        #
                        # NOTE: `helm template` has NO --reuse-values flag -- that flag
                        # only exists on `helm upgrade`/`helm install`, which manage a
                        # stored release to reuse values from. `helm template` is a pure
                        # client-side render with no release state, so passing
                        # --reuse-values here is a hard error ("unknown flag") that
                        # aborts the whole stage before the real `helm upgrade` below
                        # ever runs (Jenkins `sh` steps run with `-e` by default). Fixed
                        # by explicitly feeding the just-captured live values back in as
                        # a -f file instead -- this is the actual on-disk equivalent of
                        # what --reuse-values does internally on a real upgrade.
                        helm get values \${HELM_RELEASE} -n \${HELM_NAMESPACE} -a -o yaml > /tmp/live-values-before-\${BUILD_NUMBER}.yaml
                        helm template \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            -f /tmp/live-values-before-\${BUILD_NUMBER}.yaml \
                            -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            > /tmp/live-rendered-\${BUILD_NUMBER}.yaml
                        echo "Rendered \$(wc -l < /tmp/live-rendered-\${BUILD_NUMBER}.yaml) lines against the currently-deployed values (image tags only overridden). Archived for audit."

                       
                        helm upgrade \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            --reuse-values -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            --cleanup-on-fail --timeout 10m

                        kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-api -n \${HELM_NAMESPACE} --timeout=180s
                        kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-ui -n \${HELM_NAMESPACE} --timeout=180s
                        kubectl rollout status deployment/\${HELM_RELEASE}-partner-api -n \${HELM_NAMESPACE} --timeout=180s
                    """
                    archiveArtifacts artifacts: '/tmp/live-values-before-*.yaml, /tmp/live-rendered-*.yaml', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        success {
            script {
                def committerEmail = sh(script: "git log -1 --pretty=format:'%ae'", returnStdout: true).trim()
                def committerName  = sh(script: "git log -1 --pretty=format:'%an'", returnStdout: true).trim()
                if (committerEmail.contains('noreply')) {
                    committerEmail = 'devops@yourorg.com'
                }
                mail(
                    to: committerEmail,
                    subject: "✅ Build SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                    body: """
Hi ${committerName},

Livestock Registry build and deploy to live succeeded!

Job:    ${env.JOB_NAME}
Branch: ${env.GIT_BRANCH}
Build:  #${env.BUILD_NUMBER}
URL:    ${env.BUILD_URL}

Regards,
Jenkins
"""
                )
            }
        }
        failure {
            script {
                def committerEmail = sh(script: "git log -1 --pretty=format:'%ae'", returnStdout: true).trim()
                def committerName  = sh(script: "git log -1 --pretty=format:'%an'", returnStdout: true).trim()
                if (committerEmail.contains('noreply')) {
                    committerEmail = 'simretyibeltal@gmail.com, Pavan.ns@gmail.com'
                }
                mail(
                    to: committerEmail,
                    subject: "❌ Build FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                    body: """
Hi ${committerName},

Livestock Registry build or deployment failed. Deploy no longer uses
--atomic (dropped 2026-09-16 -- it was blocking on the already-broken
id-generator Deployment and auto-rolling-back every run), so a Deploy
failure does NOT automatically revert `live`. Check
`helm history livestock-registry -n live` and `helm status livestock-registry -n live`
to see exactly what state the release is in before assuming anything.

Job:    ${env.JOB_NAME}
Branch: ${env.GIT_BRANCH}
Build:  #${env.BUILD_NUMBER}
URL:    ${env.BUILD_URL}

Regards,
Jenkins
"""
                )
            }
        }
        always {
            sh 'docker image prune -f || true'
            sh 'docker logout ${ECR_REGISTRY} || true'
        }
    }
}