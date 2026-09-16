// Livestock-registry CI/CD pipeline.
//
//
// The old in-repo chart (helm/openg2p-livestock-registry) and its
// unfinished values-live.yaml are UNTOUCHED by this file now.

// RP_VERSION below (0.0.0-develop.296) is carried over from the original
// draft as-is

pipeline {
    agent { label 'vpn-agent2' }

    environment {
        AWS_REGION       = 'ap-south-1'
        ECR_PATH         = 'openg2p/livestock-registry'
        RP_VERSION       = '0.0.0-develop.296' 
        HELM_RELEASE     = 'livestock-registry'
        HELM_NAMESPACE   = 'live'
      
        HELM_CHART_REPO  = 'openg2p'
        HELM_CHART_URL   = 'https://openg2p.github.io/openg2p-helm'
        HELM_CHART_REF   = 'openg2p/openg2p-farmer-registry'
        HELM_CHART_VER   = '1.2.0'
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

        stage('Deploy to Live') {
            when { branch 'develop' }
            steps {
                withCredentials([file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        helm repo add ${HELM_CHART_REPO} ${HELM_CHART_URL} || true
                        helm repo update ${HELM_CHART_REPO}

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

                        # Dry-run + diff, kept even without a human gate so there's an
                        # audit trail to look at if a deploy ever needs investigating.
                        helm get values \${HELM_RELEASE} -n \${HELM_NAMESPACE} -a -o yaml > /tmp/live-values-before-\${BUILD_NUMBER}.yaml
                        helm template \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            --reuse-values -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            > /tmp/live-rendered-\${BUILD_NUMBER}.yaml
                        echo "Rendered \$(wc -l < /tmp/live-rendered-\${BUILD_NUMBER}.yaml) lines against the currently-deployed values (image tags only overridden). Archived for audit."

                        helm upgrade \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            --reuse-values -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            --atomic --cleanup-on-fail --timeout 10m

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

Livestock Registry build or deployment failed. Deploy uses --atomic, so if
the failure was in the Deploy stage, Helm should have already rolled `live`
back to the previous revision automatically -- worth confirming with
`helm history livestock-registry -n live` rather than assuming it.

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