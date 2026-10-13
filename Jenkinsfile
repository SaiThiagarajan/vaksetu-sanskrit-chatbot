// =====================================================================
//  Jenkinsfile - VakSetu : Multilingual Computational Sanskrit Chatbot
//
//  CI flow:  Checkout -> Build -> Test / Validate -> Docker Build
//            -> Smoke Test -> Result
//
//  Works on a Windows Jenkins (uses bat) and on Linux/macOS (uses sh).
// =====================================================================

// Run a command with sh on Linux/macOS or bat on Windows.
// ignoreErrors = true returns the exit code instead of failing the build.
def runCmd(String command, boolean ignoreErrors = false) {
    if (isUnix()) {
        return sh(script: command, returnStatus: ignoreErrors)
    }
    return bat(script: command, returnStatus: ignoreErrors)
}

// Python inside the project's virtual environment.
def venvPython() {
    return isUnix() ? '.venv/bin/python' : '.venv\\Scripts\\python.exe'
}

// Python used to create the venv. A Windows Jenkins service cannot see the
// per-user Microsoft Store "python" alias, so set a global PYTHON_EXE variable
// (Manage Jenkins > System > Global properties) to the full python.exe path.
def basePython() {
    return env.PYTHON_EXE ?: (isUnix() ? 'python3' : 'python')
}

pipeline {
    agent any

    options {
        skipDefaultCheckout(true)                       // checkout happens in our own stage
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    triggers {
        // Look for new commits on GitHub every ~2 minutes
        pollSCM('H/2 * * * *')
    }

    environment {
        IMAGE_NAME       = 'vaksetu-bot'
        IMAGE_TAG        = "build-${env.BUILD_NUMBER}"
        CONTAINER_NAME   = 'vaksetu-ci-check'
        PYTHONUTF8       = '1'
        PYTHONIOENCODING = 'utf-8'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Fetching source code from GitHub...'
                script {
                    def scmVars = checkout scm
                    env.COMMIT_SHORT = scmVars.GIT_COMMIT.substring(0, 7)
                    runCmd('git log -1 --oneline')
                }
            }
        }

        stage('Build') {
            steps {
                echo 'Creating Python virtual environment and installing dependencies...'
                script {
                    def python = basePython()
                    runCmd("\"${python}\" --version")
                    runCmd("\"${python}\" -m venv .venv")
                    runCmd("${venvPython()} -m pip install -r requirements-dev.txt")
                }
            }
        }

        stage('Test / Validate') {
            steps {
                echo 'Checking syntax and running unit tests...'
                script {
                    runCmd("${venvPython()} -m py_compile app.py sanskrit_engine.py")
                    runCmd("${venvPython()} -m pytest --junitxml=test-results.xml")
                    // Record the version in the source so the smoke test can check /health against it
                    runCmd("""${venvPython()} -c "from sanskrit_engine import VERSION; open('app-version.txt', 'w').write(VERSION)" """)
                    env.APP_VERSION = readFile('app-version.txt').trim()
                    echo "App version: ${env.APP_VERSION}"
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-results.xml'
                }
            }
        }

        stage('Docker Build') {
            steps {
                echo "Building Docker image ${IMAGE_NAME}:${IMAGE_TAG} ..."
                script {
                    runCmd('docker --version')
                    runCmd("docker build --label ci.build=${env.BUILD_NUMBER} --label ci.commit=${env.COMMIT_SHORT} -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest .")
                    runCmd("docker images ${IMAGE_NAME}")
                }
            }
        }

        stage('Smoke Test') {
            steps {
                echo 'Starting the new image and checking that the bot answers...'
                script {
                    runCmd("docker rm -f ${CONTAINER_NAME}", true)
                    runCmd("docker run -d --name ${CONTAINER_NAME} ${IMAGE_NAME}:${IMAGE_TAG}")
                    retry(5) {
                        sleep(time: 3, unit: 'SECONDS')
                        runCmd("""docker exec ${CONTAINER_NAME} python -c "import json, urllib.request as u; d = json.load(u.urlopen('http://localhost:5000/health')); print('health ->', d); assert d['status'] == 'ok', d; assert d['version'] == '${env.APP_VERSION}', d" """)
                    }
                    runCmd("""docker exec ${CONTAINER_NAME} python -c "import json, urllib.request as u; req = u.Request('http://localhost:5000/api/chat', data=json.dumps({'message': 'calc 6 * 7', 'language': 'en'}).encode(), headers={'Content-Type': 'application/json'}); d = json.load(u.urlopen(req)); print('chat ->', d['intent'], '|', d['reply'].splitlines()[0]); assert d['intent'] == 'calc', d; assert '6 * 7 = 42' in d['reply'], d" """)
                }
            }
        }

        stage('Result') {
            steps {
                script {
                    def summary = """VakSetu CI - build #${env.BUILD_NUMBER}
App version  : ${env.APP_VERSION}
Commit       : ${env.COMMIT_SHORT}
Docker image : ${IMAGE_NAME}:${IMAGE_TAG} (also tagged ${IMAGE_NAME}:latest)
Stages       : Checkout OK | Build OK | Test/Validate OK | Docker Build OK | Smoke Test OK
"""
                    writeFile file: 'build-info.txt', text: summary
                    echo summary
                }
                archiveArtifacts artifacts: 'build-info.txt, test-results.xml', allowEmptyArchive: true
            }
        }
    }

    post {
        always {
            script {
                runCmd("docker rm -f ${CONTAINER_NAME}", true)   // clean up the test container
            }
        }
        success {
            echo "PIPELINE SUCCESS: ${IMAGE_NAME}:${IMAGE_TAG} built and verified from commit ${env.COMMIT_SHORT}"
        }
        failure {
            echo 'PIPELINE FAILED: open the red stage in the pipeline view to see which step broke.'
        }
    }
}
