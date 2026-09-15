// Livestock-registry CI/CD pipeline — rebuilt to follow the same pattern as
// farmer-registry's Jenkinsfile (see project doc
// staging-farmer-registry-cicd-pipeline.md): CI-values heredoc + `helm
// template` dry-run/diff before any real upgrade, rather than a long chain
// of --set flags. The version pasted into chat had gotten scrambled into an
// invalid mix of at least two earlier drafts (nested `stage` blocks inside
// `stages`, a `stage` block illegally nested inside `post { success { ... }
// }`, two different image-tagging schemes, two different kubeconfig
// credential IDs, an unconditional deploy straight to `live` with no gate).
// This is a clean rewrite, not a patch of that file.
//
// IMPORTANT — read before flipping DEPLOY_TO_LIVE to true:
//
// 1. `live` is CURRENTLY running the OLD generic `openg2p/openg2p-farmer-registry`
//    chart (v1.2.0, Docker Hub `nahom25/*` images) — see
//    staging-livestock-registry-live-deployment.md. This pipeline deploys a
//    DIFFERENT chart (this repo's own helm/openg2p-livestock-registry,
//    aliasing the same `openg2p-registry` dependency farmer-registry uses).
//    The first real run of the Deploy stage is a chart-switch cutover, not
//    a routine upgrade — that's why DEPLOY_TO_LIVE defaults to false and
//    Build & Push always runs regardless of it.
//
// 2. Because of (1), `helm get values livestock-registry -n live` returns
//    values shaped for the OLD chart — NOT a valid base for this chart's
//    values schema, unlike farmer-registry's pipeline where `far` was
//    already on the same chart family. This Deploy stage therefore does NOT
//    feed that into the real `helm upgrade` (only into a side-by-side dump
//    for manual comparison). It instead expects a committed
//    `${HELM_CHART_DIR}/values-live.yaml` maintained in the repo, carrying
//    everything CI doesn't own: global hostnames, keycloak/postgres/minio
//    wiring, iamRegister.applicationDescription (the "Livestock Registry"
//    IAM-tile-name bug — see staging-livestock-registry-live-deployment.md),
//    and the dbSeed loadSampleData/loadImages/loadTemplates=false caution
//    already applied for `live` once before. THIS FILE DOES NOT EXIST YET
//    for the new chart's schema (only the old chart's equivalent has been
//    written) — author and commit it before the first DEPLOY_TO_LIVE=true
//    run, translating the values already captured in that doc.
//
// 3. RP_VERSION below (0.0.0-develop.296) is carried over from the pasted
//    draft as-is and has NOT been re-verified against this repo's actual
//    current pin. Farmer-registry's own stale Jenkinsfile had exactly this
//    bug (RP_VERSION one version behind the chart's real pin) — check it
//    against Chart.yaml / docker/sanity-tests/Dockerfile's own ARG default
//    before relying on it.
//
// 4. `db-seed`'s `loadAttributes` is baked in as `false` here from the
//    start (see the dbSeed block below) — this is the same bug documented
//    at length in farmer-registry-image-update-and-dbseed-fix.md (section
//    H): LOAD_ATTRIBUTES=true calls a master-data endpoint that 404s on
//    this cluster and aborts db-seed every time. No reason to rediscover
//    that the hard way here too.
//
// 5. CORRECTION (this rewrite): staging-jenkins-cicd-agent-setup.md and an
//    earlier draft of this file both claimed there's no staff-ui build here
//    and that it's "consumed unmodified from upstream." That's wrong — this
//    repo does build a custom staff-ui image (confirmed real Dockerfile at
//    docker/staff-ui/Dockerfile; the wrapper chart's own values.yaml comment
//    says the asset + CSS override baked in by that Dockerfile is "the whole
//    reason this image is built here rather than consumed as-is"). Without
//    a staffUi image override, the chart falls through to the wrapper
//    default `openg2p/openg2p-livestock-registry-staff-ui:0.0.0-develop` on
//    Docker Hub — a repository that was never actually published, which is
//    exactly the "repository does not exist" failure seen on staff-portal-ui.
//    Fixed below: staff-ui is now a 6th built-and-pushed component, with the
//    matching registry.staffUi image override in the CI values heredoc.

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
  staffUi:
    image:
      repository: ${env.ECR_REGISTRY}/${ECR_PATH}/staff-ui
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