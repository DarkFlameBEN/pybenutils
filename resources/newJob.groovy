pipeline {
    agent {label "master-slave"}
    options {
        buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '31', numToKeepStr: '100'))
    }
    parameters {
        string name: 'EMAIL', defaultValue: '', description: 'Email recipient list, seperated by ; sign', trim: true
        string name: 'NODES', defaultValue: 'windows10 windows11 bigsur monterey', description: 'Node names separated by spaces', trim: true
        string name: 'BRANCH', defaultValue: 'master', description: 'Repo branch', trim: true
        string name: 'SUITE_NAME', defaultValue: 'MY_SUITE', description: 'The current suite name', trim: true
        string name: 'TIMEOUT', defaultValue: '24', description: 'Timeout in hours for the execution phase', trim: true
        booleanPacram name: 'TEST_PARAM', defaultValue: false, description: 'boolean test parameter'
    }
    stages{
        stage('Unified flow'){
            steps{
                script{
                    flowManager.flowStart(params)
                }
            }
        }
    }
    post{
        always {
            script{
                flowManager.EMAIL_TAG = 'TEST'
                flowManager.flowTeardown()
            }
        }
    }
}