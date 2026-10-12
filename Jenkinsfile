// Declarative pipeline: build -> test -> scan -> package -> deploy dev -> smoke -> approve -> deploy prod (with rollback)
pipeline {
  agent any

  options {
    timestamps()
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20'))
    disableConcurrentBuilds()
  }

  environment {
    IMAGE   = 'loan-api'
    NETWORK = 'cicd-lab'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
          currentBuild.displayName = "#${env.TAG}"
        }
        sh 'mkdir -p reports'
      }
    }

    stage('Secret scan') {
      // Runs before anything else: if a secret was committed, stop immediately.
      steps {
        sh 'gitleaks detect --source . --redact --report-format json --report-path reports/gitleaks.json'
      }
    }

    stage('Install deps') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          pip install --quiet --upgrade pip
          pip install --quiet -r requirements-dev.txt
        '''
      }
    }

    stage('Quality gates') {
      parallel {
        stage('Lint') {
          steps { sh '. .venv/bin/activate && flake8 app tests' }
        }
        stage('Unit tests') {
          steps {
            sh '''
              . .venv/bin/activate
              pytest -q --junitxml=reports/junit.xml \
                     --cov=app --cov-report=xml:reports/coverage.xml --cov-fail-under=80
            '''
          }
        }
        stage('SAST (bandit)') {
          steps { sh '. .venv/bin/activate && bandit -r app -ll -f txt -o reports/bandit.txt' }
        }
      }
    }

    stage('Build image') {
      steps {
        sh 'docker build --pull --build-arg APP_VERSION=$TAG -t $IMAGE:$TAG .'
      }
    }

    stage('Image scan') {
      steps {
        sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed --no-progress $IMAGE:$TAG'
      }
    }

    stage('Deploy DEV') {
      steps {
        script { deploy('dev', '8081') }
      }
    }

    stage('Smoke test DEV') {
      steps {
        script { smokeTest('loan-api-dev') }
      }
    }

    stage('Approve PROD') {
      steps {
        timeout(time: 30, unit: 'MINUTES') {
          input message: "Deploy ${env.TAG} to PROD?", ok: 'Deploy'
        }
      }
    }

    stage('Deploy PROD') {
      steps {
        script {
          // Remember what is running now so we can roll back
          def previous = sh(script: "docker inspect -f '{{.Config.Image}}' loan-api-prod 2>/dev/null || true",
                            returnStdout: true).trim()
          deploy('prod', '8090')
          try {
            smokeTest('loan-api-prod')
          } catch (err) {
            if (previous) {
              echo "Smoke test failed - rolling back to ${previous}"
              deploy('prod', '8090', previous)
            }
            error("PROD deploy of ${env.TAG} failed and was rolled back")
          }
        }
      }
    }
  }

  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
      archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/**'
      cleanWs()
    }
    success { echo "Pipeline OK - ${env.TAG}" }
    failure { echo "Pipeline FAILED at build ${env.BUILD_NUMBER} - check the stage view" }
  }
}

// ---------- helpers ----------
def deploy(String envName, String hostPort, String image = null) {
  def img = image ?: "${env.IMAGE}:${env.TAG}"
  sh """
    docker rm -f loan-api-${envName} || true
    docker run -d --name loan-api-${envName} \
      --network ${env.NETWORK} \
      --restart unless-stopped \
      -p 127.0.0.1:${hostPort}:5000 \
      ${img}
  """
}

def smokeTest(String host) {
  sh """
    for i in \$(seq 1 15); do
      curl -fs http://${host}:5000/health && break
      echo "waiting for ${host}... (\$i)"; sleep 2
    done
    curl -fs http://${host}:5000/health | grep -q '"status":"ok"'
    curl -fs -X POST http://${host}:5000/api/v1/quote \
         -H 'Content-Type: application/json' \
         -d '{"principal":1000000,"annual_rate":12,"months":12}' | grep -q '88848.79'
    echo "Smoke test passed for ${host}"
  """
}
