
pipeline {
    agent { label 'vpn-agent2' }
 
    parameters {
        booleanParam(
            name: 'DEPLOY_TO_LIVE',
            defaultValue: false,
            description: 'Also run the Deploy stage against the live namespace. Leave OFF until the chart-switch cutover (see header comment) has been done deliberately.'
        )
    }
 
    environment {
        AWS_REGION     = 'ap-south-1'
        ECR_PATH       = 'openg2p/livestock-registry'
        RP_VERSION     = '0.0.0-develop.296' // TODO verify — see header note 3
        HELM_RELEASE   = 'livestock-registry'
        HELM_NAMESPACE = 'live'
        HELM_CHART_DIR = 'helm/openg2p-livestock-registry'
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
                        def components = ['staff-api', 'partner-api', 'celery', 'db-seed', 'sanity-tests']
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
            when {
                allOf {
                    branch 'develop'
                    expression { return params.DEPLOY_TO_LIVE }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'staging-rke2-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                        helm repo add openg2p-gitlab \
                            https://gitlab.com/api/v4/projects/84460547/packages/helm/stable || true
                        helm dependency build ${HELM_CHART_DIR}
 
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
    loadAttributes: false
  sanity:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/sanity-tests
      tag: "${env.IMAGE_TAG}"
EOF
 
                        # Dump the OLD chart's current live values side-by-side for manual
                        # comparison ONLY -- see header note 2. Never fed into the real
                        # upgrade below; this chart needs its own values-live.yaml.
                        helm get values ${HELM_RELEASE} -n ${HELM_NAMESPACE} -a -o yaml > /tmp/live-values-old-chart-\${BUILD_NUMBER}.yaml || true
 
                        helm template ${HELM_RELEASE} ${HELM_CHART_DIR} -n ${HELM_NAMESPACE} \
                            -f ${HELM_CHART_DIR}/values-live.yaml \
                            -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            > /tmp/live-new-\${BUILD_NUMBER}.yaml
                        echo "Rendered \$(wc -l < /tmp/live-new-\${BUILD_NUMBER}.yaml) lines. This is a CHART-SWITCH CUTOVER for the live namespace -- review this output by hand (and against /tmp/live-values-old-chart-\${BUILD_NUMBER}.yaml, which is the OLD chart's values and NOT directly comparable) before trusting an automatic run."
 
                        helm upgrade --install ${HELM_RELEASE} ${HELM_CHART_DIR} -n ${HELM_NAMESPACE} \
                            -f ${HELM_CHART_DIR}/values-live.yaml \
                            -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            --timeout 20m
 
                        kubectl rollout status deployment/${HELM_RELEASE}-staff-portal-api -n ${HELM_NAMESPACE} --timeout=180s
                        kubectl rollout status deployment/${HELM_RELEASE}-partner-api -n ${HELM_NAMESPACE} --timeout=180s
                    """
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
 
Livestock Registry build${params.DEPLOY_TO_LIVE ? ' and deployment' : ''} succeeded!
 
Job:    ${env.JOB_NAME}
Branch: ${env.GIT_BRANCH}
Build:  #${env.BUILD_NUMBER}
URL:    ${env.BUILD_URL}
Deployed to live: ${params.DEPLOY_TO_LIVE}
 
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
 
Livestock Registry build or deployment failed.
 
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