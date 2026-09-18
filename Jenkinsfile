pipeline {
    agent { label 'vpn-agent2' }
    // One run at a time: merging several PRs back to back queued overlapping
    // runs whose helm upgrades collided ("another operation in progress"),
    // which is what showed up as a failed db-seed on dev on 2026-09-18.
    options { disableConcurrentBuilds() }

    environment {
        AWS_REGION       = 'ap-south-1'
        ECR_PATH         = 'openg2p/livestock-registry'
        RP_VERSION       = '0.0.0-develop.296' // TODO verify — see header note
        HELM_RELEASE     = 'livestock-registry'
        HELM_NAMESPACE   = 'live'
        // The chart actually running in `live` today — NOT this repo's own
        // helm/openg2p-livestock-registry. See header comment.
        HELM_CHART_REPO  = 'openg2p'
        HELM_CHART_URL   = 'https://openg2p.github.io/openg2p-helm'
        HELM_CHART_REF   = 'openg2p/openg2p-farmer-registry'
        HELM_CHART_VER   = '1.2.0'

        // Dev-cluster deploy target (see header comment above). Separate
        // physical cluster from HELM_NAMESPACE/staging-rke2-kubeconfig
        // above; same chart/release-name convention, different kubeconfig.
        // Dedicated credential for the dedicated live:livestock-ci
        // ServiceAccount (ci/k8s/livestock-deploy-rbac.yaml) 
 
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
 
            // image-tag overlay file instead of two copies that could drift.
            // Content is cluster/namespace-agnostic (image repo+tag only) —
            // safe to reuse verbatim against either kubeconfig.
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
           
            // (helm/openg2p-livestock-registry) with its checked-in
            // values.yaml used AS-IS -- no separate overlay/draft values
            // file. That file's own header states its intended CI contract
            // explicitly: "Only the tag is CI-rewritten in lockstep with
            // the chart version" -- everything else (global registryVariant,
            // idgenerator pools, sanity regType/scopes, iamRegister
            // description, dbSeed loader flags) is registry-correct as
            // committed and isn't CI's to touch. So this stage overrides
            // the six image refs that are genuinely CI-owned (repository+tag,
            // via --set, matching this pipeline's Build & Push stage) and
            // layers values-dev.yaml on top for everything that belongs to
            // the DEV CLUSTER rather than to the registry.
            //
            // values-dev.yaml was added because deploying values.yaml as-is
            // did not work: the chart's defaults address the release on
            // `*.<namespace>.openg2p.org`, a domain that does not exist on
            // this box. The pods ran, but on hostnames nothing resolved and
            // no Istio Gateway admitted -- so dev went on serving the August
            // hand-installed `farmer-registry` release and none of the
            // September merges were visible on the dev URL. That file also
            // carries the dev cluster's MinIO endpoint (the placeholder one
            // failed db-seed, which took the release to `failed`), the moved
            // GitLab path for id-generator, and memory limits for the two
            // celery pods, both of which were being OOMKilled at the chart
            // defaults. Each override is justified in place there.
            //
            // It sets `global.registryHostname` to the public dev hostname,
            // so the release's OWN staff-ui VirtualService owns that URL and
            // every merge reaches it with no manual step. That replaces the
            // hand-applied `pub-staff-portal-ui` VirtualService, which has to
            // be deleted ONCE -- see README-dev.md next to values-dev.yaml.
            // Until it is, it and this release's VirtualService claim the
            // same host on the same Gateway, and the older one wins.
            //
            // `helm upgrade --install` (not `--reuse-values`) is used
            // deliberately: every run supplies the full intended value set
            // (checked-in values.yaml + these --set flags) from repo state,
            // so there's nothing to drift out of sync with and no
            // dependency on a prior release already existing -- unlike the
            // staging stage below, which targets an already-running release
            // built from a DIFFERENT chart lineage and has no in-repo
            // values file to be declarative from.
            //
            // `live`'s shared-services layer
            // (`commons`/`commons-services` releases, own
            // Keycloak/Postgres/MinIO) is already deployed and healthy --
            // no bring-up needed. `live` ALSO already has an existing
            // `farmer-registry` release (STATUS: failed, pods Running)
            // that this NEW `livestock-registry` release deploys alongside
           
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
                            # Written workspace-relative (not /tmp/...) so archiveArtifacts
                            # below can actually find it -- see header UPDATE note.
                            helm template \${HELM_RELEASE} ./helm/openg2p-livestock-registry -n \${HELM_NAMESPACE_DEV} \
                                -f ./helm/openg2p-livestock-registry/values-dev.yaml \
                                \$IMAGE_SET_FLAGS \
                                > dev-rendered-\${BUILD_NUMBER}.yaml
                            echo "Rendered \$(wc -l < dev-rendered-\${BUILD_NUMBER}.yaml) lines from the in-repo chart's values.yaml + values-dev.yaml + image overrides. Archived for audit."

                            # Guard against exactly the failure described above: a
                            # render still carrying the chart's placeholder domain
                            # means the dev overlay did not take effect, and the
                            # deploy would land on hostnames nothing resolves.
                            if grep -q 'openg2p\\.org' dev-rendered-\${BUILD_NUMBER}.yaml; then
                                echo "FATAL: rendered manifests still reference the placeholder domain openg2p.org:"
                                grep -n 'openg2p\\.org' dev-rendered-\${BUILD_NUMBER}.yaml | head -20
                                exit 1
                            fi

                            # No --atomic here either, same reasoning as staging: if
                            # id-generator's GitLab-403 ImagePullBackOff is present on
                            # this cluster too (same private-registry credential
                            # problem, likely cluster-agnostic — not yet independently
                            # confirmed on dev), --wait would block the full timeout
                            # and auto-rollback would discard a good deploy.
                            #
                            # livestock-ci's RBAC is
                            # deliberately namespace-scoped-only (no ClusterRoleBinding),
                            # so this flag can only fail here
                            
                            helm upgrade --install \${HELM_RELEASE} ./helm/openg2p-livestock-registry -n \${HELM_NAMESPACE_DEV} \
                                -f ./helm/openg2p-livestock-registry/values-dev.yaml \
                                \$IMAGE_SET_FLAGS \
                                --cleanup-on-fail --timeout 10m

                            kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-api -n \${HELM_NAMESPACE_DEV} --timeout=180s
                            kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-ui -n \${HELM_NAMESPACE_DEV} --timeout=180s
                            kubectl rollout status deployment/\${HELM_RELEASE}-partner-api -n \${HELM_NAMESPACE_DEV} --timeout=180s
                        """
                        archiveArtifacts artifacts: 'dev-rendered-*.yaml', allowEmptyArchive: true
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
                        # Written workspace-relative (not /tmp/...) so archiveArtifacts
                        # below can actually find them
                        helm get values \${HELM_RELEASE} -n \${HELM_NAMESPACE} -a -o yaml > live-values-before-\${BUILD_NUMBER}.yaml
                        helm template \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            -f live-values-before-\${BUILD_NUMBER}.yaml \
                            -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            > live-rendered-\${BUILD_NUMBER}.yaml
                        echo "Rendered \$(wc -l < live-rendered-\${BUILD_NUMBER}.yaml) lines against the currently-deployed values (image tags only overridden). Archived for audit."

                        # NOTE (added 2026-09-16, after the first real deploy got stuck twice):
                        # --atomic (and --wait, which it implies) makes Helm block until
                        # EVERY Deployment in the release is fully rolled out -- not just
                        # the ones this overlay touches. `live` has a pre-existing, already
                        # documented, not-fixable-from-here problem on
                        # livestock-registry-id-generator (a GitLab container registry
                        # pull started 403'ing anonymously -- see the outage postmortem's
                        # "Open -- id-generator GitLab pull failure" section): its current
                        # ReplicaSet can never finish rolling out, so a --wait'd upgrade
                        # blocks for the full --timeout on THAT unrelated Deployment, then
                        # --atomic auto-rolls-back the whole release -- discarding whatever
                        # real fix this run was trying to land, every single time, until
                        # id-generator's GitLab access is restored upstream (not an infra
                        # fix). --cleanup-on-fail is kept (it doesn't require --atomic
                        # and doesn't wait) for some safety net on a genuine hook failure;
                        # the explicit `kubectl rollout status` checks below already cover
                        # verifying the three deployments this pipeline actually cares
                        # about, without id-generator poisoning the wait.
                        helm upgrade \${HELM_RELEASE} ${HELM_CHART_REF} --version ${HELM_CHART_VER} -n \${HELM_NAMESPACE} \
                            --reuse-values -f /tmp/values-live-cicd-\${BUILD_NUMBER}.yaml \
                            --cleanup-on-fail --timeout 10m

                        kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-api -n \${HELM_NAMESPACE} --timeout=180s
                        kubectl rollout status deployment/\${HELM_RELEASE}-staff-portal-ui -n \${HELM_NAMESPACE} --timeout=180s
                        kubectl rollout status deployment/\${HELM_RELEASE}-partner-api -n \${HELM_NAMESPACE} --timeout=180s
                    """
                    archiveArtifacts artifacts: 'live-values-before-*.yaml, live-rendered-*.yaml', allowEmptyArchive: true
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