import com.ironsrc.aws.Ec2Manager
import com.ironsrc.aws.SqsManager
import com.ironsrc.aws.AwsService
import com.ironsrc.aws.LambdaManager

/**
 * Create a new {@link com.ironsrc.aws.Ec2Manager} object oriented for executing EC2 operations in a specific region with a specific user.
 *
 *  @param region AWS region in which all operations will be executed
 *  @param credentialsId Jenkins defined AWS credentials ID
 *  @return New {@link com.ironsrc.aws.Ec2Manager} initialized with the given parameters
 */
def createEc2Manager(String region, String credentialsId) {
    return Ec2Manager.create(this, region, credentialsId)
}

/**
 * Create a new {@link com.ironsrc.aws.SqsManager} object oriented for executing SQS operations in a specific region with a specific user.
 *
 *  @param region AWS region in which all operations will be executed
 *  @param credentialsId Jenkins defined AWS credentials ID
 *  @param queueUrl URL of the queue on which all operations will be executed
 *  @return New {@link com.ironsrc.aws.SqsManager} instance initialized with the given parameters
 */
def createSqsManager(String region, String credentialsId, String queueUrl) {
    return SqsManager.create(this, region, credentialsId, queueUrl)
}

/**
 *  Create a new {@link com.ironsrc.aws.LambdaManager} object oriented for executing LAMBDA operations in a specific region with a specific user.
 *
 *  @param region AWS region in which all operations will be executed
 *  @param credentialsId Jenkins defined AWS credentials ID
 *  @return New {@link com.ironsrc.aws.LambdaManager} initialized with the given parameters
 */
def createLambdaManager(String region, String credentialsId) {
    return LambdaManager.create(this, region, credentialsId)
}

/**
 * Run the given api command using the AWS command line interface.
 *
 * @param region AWS region in which all operations will be executed
 * @param credentialsId Jenkins defined AWS credentials ID
 * @param command AWS command to execute (via AWS CLI)
 * @return The output of the command as string
 */
def call(String region, String credentialsId, String command){
    assert AwsService.awsRegions.contains(region): "Region parameter has an invalid value: ${region}\nSuported regions are: ${AwsService.awsRegions}"
    assert credentialsId: "CredentialsId parameter cannot be empty"
    assert command: "Command parameter cannot be empty"
    withAWS(region: region, credentials: credentialsId) {
        return cmd(script: "aws ${command}", returnStdout: true)
    }
}