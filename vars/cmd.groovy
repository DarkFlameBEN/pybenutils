
/**
 * Run the given command according to the relevant operating system (Batch on Windows, Shell on Linux)
 *
 * @param script The script to execute (shell script on Linux, Batch script on Windows)
 * @param label Label to be displayed in the pipeline step view and blue ocean details, instead of the step type (optional)
 * @param returnStatus Normally, a script which exits with a nonzero status code will cause the step to fail with an exception.
 *    If this option is checked, the return value of the step will instead be the status code (optional)
 * @param returnStdout If checked, standard output from the task is returned as the step value as a String,
 *    rather than being printed to the build log (optional)
 * @return Return the relevant data according to the returnStatus and the returnStdout parameters
 */
def call(String script, String label = '', Boolean returnStatus = false, Boolean returnStdout = false){
    def result
    if (isUnix()) {
        result = sh script: script, label: label, returnStatus: returnStatus, returnStdout: returnStdout
    }
    else {
        result = bat script: script, label: label, returnStatus: returnStatus, returnStdout: returnStdout
    }
    return result
}

/**
 * Run the given command according to the relevant operating system (Batch on Windows, Shell on Linux)
 *
 * @param params A map of key values parameters to be used, supports the following parameters:
 * String script - The script to execute (shell script on Linux, Batch script on Windows)
 * String label - Label to be displayed in the pipeline step view and blue ocean details, instead of the step type (optional)
 * Boolean returnStatus - Normally, a script which exits with a nonzero status code will cause the step to fail with an exception.
 *    If this option is checked, the return value of the step will instead be the status code (optional)
 * Boolean returnStdout - If checked, standard output from the task is returned as the step value as a String,
 *    rather than being printed to the build log (optional)
 * @return Return the relevant data according to the returnStatus and the returnStdout parameters
 */
def call(Map params){
    assert params.script : "The script parameter cannot be empty"
    call(params.script.toString(),
            params.label ? params.label.toString() : '',
            params.returnStatus ? params.returnStatus.toBoolean() : false,
            params.returnStdout ? params.returnStdout.toBoolean() : false,
    )
}