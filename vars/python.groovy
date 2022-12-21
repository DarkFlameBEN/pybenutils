import com.ironsrc.python.VirtualEnv
import groovy.transform.Field

/**
 * Will be used to store {@link com.ironsrc.python.VirtualEnv} instance for each executing Jenkins Node
 */
@Field
def envMap = [:]

/**
 * Will be used to store operating system identifier (isUnix Boolean) for each executing Jenkins Node
 */
@Field
def osTypeMap = [:]

/**
 * Get the operating system type of the current executing node
 * @return True if current node is a unix like operating system, False if it is a Windows system.
 */
def getUnixOS() {
    return osTypeMap.containsKey(env.NODE_NAME) ? osTypeMap[env.NODE_NAME] : osTypeMap.get(env.NODE_NAME, isUnix())
}

/**
 * Run a Python script
 * Upon setting the useVirtualEnv parameter to true a virtual environment will be created in which the script will be executed.
 * The virtual environment will be created per executing Node, and will be saved for further executions made on the same Node.
 * @param script The script to execute
 * @param useVirtualEnv True for running the python script inside a Node dedicated virtual environment (Default - false)
 * @param returnStatus Normally, a script which exits with a nonzero status code will cause the step to fail with an exception.
 *    If this option is checked, the return value of the step will instead be the status code (optional)
 * @param returnStdout If checked, standard output from the task is returned as the step value as a String,
 *    rather than being printed to the build log (optional)
 * @return  return the relevant data according to the returnStatus and the returnStdout parameters
 */
def call(String script, Boolean useVirtualEnv = false, Boolean returnStatus = false, Boolean returnStdout = false){
    catchPythonError {
        if (useVirtualEnv) {
            def virtualEnv = envMap[env.NODE_NAME] ?: envMap.get(env.NODE_NAME, createVirtualEnv('env'))
            virtualEnv.run(script)
        } else {
            Map parameters = [
                script: "${unixOS ? 'python3' : 'python'} ${script}",
                label: "Python: ${script}",
                returnStatus: returnStatus,
                returnStdout: returnStdout
            ]
            def res = cmd(parameters)
            return res
        }
    }
}

/**
 * Run a Python script
 * Upon setting the useVirtualEnv parameter to true a virtual environment will be created in which the script will be executed.
 * The virtual environment will be created per executing Node, and will be saved for further executions made on the same Node.
 * @param script The script to execute
 * @param useVirtualEnv True for running the python script inside a Node dedicated virtual environment (Default - false)
 * @param returnStatus Normally, a script which exits with a nonzero status code will cause the step to fail with an exception.
 *    If this option is checked, the return value of the step will instead be the status code (optional)
 * @param returnStdout If checked, standard output from the task is returned as the step value as a String,
 *    rather than being printed to the build log (optional)
 * @return  return the relevant data according to the returnStatus and the returnStdout parameters
 */
def call(HashMap conf){
    return call(conf.script, conf.useVirtualEnv, conf.returnStatus, conf.returnStdout)
}

/**
 * Create a new {@link com.ironsrc.python.VirtualEnv} instance.
 * @param envName The name of the folder in which the Virtual environment will be created
 *     If given empty the Virtual environment is stored under the system temporary directory that is unique for each build number
 * @param python Python version or absolute path to Python executable.
 *     On Windows, this should be a Cygwin-style path, but <strong>without the {@code .exe} extension</strong>,
 *     for example: {@code /c/Python27/python}
 * @return New {@link com.ironsrc.python.VirtualEnv} instance.
 */
VirtualEnv createVirtualEnv(String envName, String python = '') {
    return VirtualEnv.create(this, envName, python)
}

/**
 * Run a Python script (script will be written to file and executed)
 * @param script The python script to execute
 * @param useVirtualEnv True for running the python command inside a virtual environment
 */
def runScript(String script, Boolean useVirtualEnv){
    println "Running the following script: ${script}"
    def fileName = "script_${new Date().getTime()}.py"
    writeFile file: fileName, text: script
    call(fileName, useVirtualEnv)
}

/**
 * Install Requirements from a given file using PIP
 * Attention: On Unix type system, if the virtual environment option is NOT used the '--user' flag will be added to the install command
 * @param filePath Path to the requirements file
 *     If the requirements file resides in the root execution folder passing the file name is sufficient)
 * @param useVirtualEnv True for running the python command inside a virtual environment
 */
def installRequirements(String filePath, Boolean useVirtualEnv = false) {
    def userFlag = !useVirtualEnv && unixOS ? ' --user' : ''
    call("-m pip install -r ${filePath} -U${userFlag}", useVirtualEnv)
}

/**
 * List installed packages, including editables. (Packages are listed in a case-insensitive sorted order.)
 * Attention: On Unix type system, if the virtual environment option is NOT used the '--user' flag will be added to the install command
 * @param useVirtualEnv True for running the python command inside a virtual environment
 */
def pipList(Boolean useVirtualEnv = false) {
    def userFlag = !useVirtualEnv && unixOS ? ' --user' : ''
    call("-m pip list${userFlag}", useVirtualEnv)
}

/**
 * Create a python source distribution
 * <strong>Requires setup.py file to exists in the execution folder</strong>
 * @param format Package format: gztar (Default), zip, bztar, ztar, tar
 */
def createSourceDistribution(String format = 'gztar'){
    assert fileExists('setup.py') : "The 'setup.py' file was not found in the execution folder"
    call("setup.py sdist --formats=${format}")
}

/**
 * Execute tests using using pytest-runner (on setuptools based project)
 * <strong>Requires setup.py file to exists in the execution folder with proper configuration</strong>
 * @param useVirtualEnv True for running the python command inside a virtual environment
 */
def runTests(Boolean useVirtualEnv = false){
    assert fileExists('setup.py') : "The 'setup.py' file was not found in the execution folder"
    call("setup.py test", useVirtualEnv)
}

/**
 * Installs a given packages from the given URL
 * @param packageUrl The Url in which to find the requested package. Example: https://ironsrc.jfrog.io/ironsrc/api/pypi/pypi-local-release/simple
 * @param packageName The package name (automation_keywords) with or without the version
 * @param version A specific version of the package to install. <strong>If empty the latest available version will be installed.</strong>
 * @param useVirtualEnv True for running the python command inside a virtual environment
 */
def installPackageFromUrl(String packageUrl, String packageName, String version, Boolean useVirtualEnv = false){
    // Extract the domain form the url
    String domain = (new URI(packageUrl)).getHost()
    if(domain.startsWith("www.")) {
        domain = domain.substring(4)
    }
    // Uninstall the package
    call("-m pip uninstall -y ${packageName}", useVirtualEnv)
    // Run the installation command
    def userFlag = !useVirtualEnv && unixOS ? ' --user' : ''
    packageName = version ? "${packageName}==${version}" : packageName
    call("-m pip install --trusted-host ${domain} --extra-index-url ${packageUrl} --upgrade --no-cache-dir ${packageName}${userFlag}", useVirtualEnv)
}

/**
 * Catch a shell\bat exception and try to extract and throw the python exception from the console logs
 * In case the function fails to extract the python exception, the original exception will be thrown
 * @param body The closure (code section) that executes the python code
 */
def catchPythonError(Closure body) {
    try {
        body()
    }
    catch (InterruptedException aborted) {
        throw aborted
    }
    catch (Exception originalErr) {
        def exception
        try {
            // Get last 50 log lines from the console as a list
            def lines = currentBuild.rawBuild.getLog(50)
            // Remove all lines prior and including the first line that contains the 'Traceback' string
            lines = lines.drop(lines.findIndexOf { it ==~ /.*Traceback \(.*/ } + 1)
            // Join all lines, remove timestamps (if they exist), remove whitespace and indentation and split again
            lines = lines.join('\n').replaceAll(/\[.*?\]/, '').stripIndent().split('\n')
            // Find the start index of the exception by looking for the first line that doesn't start with a whitespace
            def startIndex = lines.findIndexOf { it ==~ /^(?!\s).*$/ }
            // Find the end index of the exception by looking for a line that starts with 'The above exception' after the exception line
            def endIndex = (lines.findIndexOf { it ==~ /^The above exception.*$/ } -1)
            if(startIndex > 0) {
                // Use both indexes (if relevant) to take the exception lines and join them into a string
                exception = (endIndex > 0 ? lines.drop(startIndex).take(endIndex - startIndex) : lines.drop(startIndex)).join('\n')
            }
            else {  // the python exception was not found
                throw new Exception("Failed to locate the exception in the log.")
            }
        }
        catch (Exception err) {
            println "Failed to extract python exception: ${err}"
            throw originalErr // throw the original exception
        }
        error exception
    }
}