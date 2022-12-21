
/**
 * Download files from the given Artifactory server
 * More info can be found at https://www.jfrog.com/confluence/display/JFROG/Working+With+Pipeline+Jobs+in+Jenkins
 *
 * @param params A map of key values parameters to be used, supports the following parameters:
 *
 * <strong>Server Details</strong>
 * String serverId (Mandatory) - Artifactory server id that is defined in Jenkins (under Manage | Configure System).
 * or
 * String artifactoryUrl - Artifactory URL.
 * String username - Artifactory username with access rights to the requested files.
 * String password - Artifactory password.
 *
 * <strong>Download Details</strong>
 * String pattern (Mandatory) - Specifies the source path in Artifactory, from which the artifacts should be downloaded,
 *    use the following format: [repository name]/[repository path]. You can use wildcards to specify multiple artifacts.
 * String target (Optional) - Specifies the local file system path to which artifacts which should be downloaded (Default: ./).
 * Boolean flat (Optional) - If true (Default), artifacts are downloaded to the exact target path specified and their hierarchy in the source repository is ignored.
 *    If false, artifacts are downloaded to the target path in the file system while maintaining their hierarchy in the source repository.
 * Boolean recursive (Optional) - If true (Default), artifacts are also downloaded from sub-paths under the specified path in the source repository.
 *    If false, only artifacts in the specified source path directory are downloaded.
 * Boolean explode (Optional) - If true, the downloaded archive file is extracted after the download. (Default is false)
 *    The archived file itself is deleted locally. The supported archive types are: zip, tar; tar.gz; and tgz
 * List excludePatterns (Optional) - A list of patterns to be excluded from downloading.
 *    Unlike the "pattern" property, "excludePatterns" must NOT include the repository as part of the pattern's path.
 *    You can use wildcards to specify multiple artifacts. For example: ["*.sha1","*.md5"].
 * Boolean failNoOperation - Fail the build in case no files are downloaded.
 *
 * @return List of file paths (full paths) of all the files that were downloaded from the artifactory server.
 */
def download(Map params) {
    println "Downloading files from Artifacotry"
    assert params.serverId || (params.artifactoryUrl && params.username && params.password) : "Missing Artifactory Server Details"
    assert params.pattern : "The 'pattern' parameter cannot be empty"

    // Create the server object
    def server
    if(params.serverId) {
        server = Artifactory.server params.serverId
    }
    else {
        server = Artifactory.newServer url: params.artifactoryUrl, username: params.username, password: params.password
    }

    // Format the exclude patterns if given
    if(params.excludePatterns) {
        params.excludePatterns = params.excludePatterns.collect{ "\"${it}\"" }
    }

    // Create the download request
    def downloadSpec = """{
                            "files": [
                                {
                                    "pattern": "${params.pattern}",
                                    "target": "${params.target ?: './'}",
                                    "recursive": "${convertToBoolean(params.recursive,true)}",
                                    "flat": "${convertToBoolean(params.flat, true)}",
                                    "explode": "${convertToBoolean(params.explode, false)}",
                                    "excludePatterns": [${params.excludePatterns ? params.excludePatterns.join(',') : ''}]
                                }
                            ]
                          }"""
    println downloadSpec

    // Download the file
    def result = server.download(spec: downloadSpec, failNoOp: convertToBoolean(params.failNoOperation, false))
    return result.getDependencies().collect {it.localPath}
}

/**
 * Upload files to the given Artifactory server
 * More info can be found at https://www.jfrog.com/confluence/display/JFROG/Working+With+Pipeline+Jobs+in+Jenkins
 *
 * @param params A map of key values parameters to be used, supports the following parameters:
 *
 * <strong>Server Details</strong>
 * String serverId (Mandatory) - Artifactory server id that is defined in Jenkins (under Manage | Configure System).
 * or
 * String artifactoryUrl - Artifactory URL.
 * String username - Artifactory username with access rights to the requested files.
 * String password - Artifactory password.
 *
 * <strong>Upload Details</strong>
 * String pattern (Mandatory) - Specifies the local file system path to artifacts which should be uploaded to Artifactory.
 *    You can specify multiple artifacts by using wildcards or a regular expression as designated by the regexp property.
 *    If you use a regexp, you need to escape any reserved characters (such as ".", "?", etc.) used in the expression using a backslash "\".
 * String target (Mandatory) - Specifies the target path in Artifactory in the following format: [repository_name]/[repository_path].
 *    If the pattern ends with a slash, for example "repo-name/a/b/", then "b" is assumed to be a folder in Artifactory and the files are uploaded into it.
 *    In the case of "repo-name/a/b", the uploaded file is renamed to "b" in Artifactory.
 * Boolean flat (Optional) - If true (Default), artifacts are uploaded to the exact target path specified and their hierarchy in the source file system is ignored.
 *    If false, artifacts are uploaded to the target path while maintaining their file system hierarchy.
 * Boolean recursive (Optional) - If true (Default), artifacts are also collected from sub-directories of the source directory for upload.
 *    If false, only artifacts specifically in the source directory are uploaded.
 * Boolean regexp (Optional) - If true the command will interpret the pattern property as a regular expression.
 *    If false (Default), the command will interpret the pattern property as a wild-card expression.
 * Boolean explode (Optional) - The uploaded archive file is extracted after it is uploaded. (Default is false)
 *    The archived file itself is not saved in Artifactory. The supported archive types are: zip, tar; tar.gz; and tgz
 * List excludePatterns (Optional) - A list of patterns to be excluded from uploading. For example: ["*.sha1","*.md5"]
 *    Allows using wildcards or a regular expression as designated by the regexp property.
 *    If you use a regexp, you need to escape any reserved characters (such as ".", "?", etc.) used in the expression using a backslash "\".
 * Boolean failNoOperation - Fail the build in case no files were uploaded.
 *
 * @return List of links (full url) to all files that were uploaded to the artifactory server.
 */
def upload(Map params) {
    println "Uploading files from Artifacotry"
    assert params.serverId || (params.artifactoryUrl && params.username && params.password) : "Missing Artifactory Server Details"
    assert params.pattern : "The 'pattern' parameter cannot be empty"
    assert params.target : "The 'target' parameter cannot be empty"

    // Create the server object
    def server
    if (params.serverId) {
        server = Artifactory.server params.serverId
    }
    else {
        server = Artifactory.newServer url: params.artifactoryUrl, username: params.username, password: params.password
    }

    // Format the exclude patterns if given
    if (params.excludePatterns){
        params.excludePatterns = params.excludePatterns.collect{ "\"${it}\"" }
    }

    // Create the upload request
    def uploadSpec = """{
                            "files": [
                                {
                                    "pattern": "${params.pattern}",
                                    "target": "${params.target}",
                                    "recursive": "${convertToBoolean(params.recursive,true)}",
                                    "flat": "${convertToBoolean(params.flat, true)}",
                                    "regexp": "${convertToBoolean(params.regexp, false)}",
                                    "explode": "${convertToBoolean(params.explode, false)}",
                                    "excludePatterns": [${params.excludePatterns ? params.excludePatterns.join(',') : ''}]
                                }
                            ]
                          }"""
    println uploadSpec

    // Upload the file
    def result = server.upload(spec: uploadSpec, failNoOp: convertToBoolean(params.failNoOperation, false))
    return result.getArtifacts().collect {"${server.getUrl()}/${it.remotePath}"}
}

/**
 * Constructs the Full PyPI (Python Package Index) Api Url for the given Artifactory repository
 *
 * @param serverId Artifactory server id that is defined in Jenkins (under Manage | Configure System)
 * @param credentialsId Jenkins defined Artifactory credentials ID (Username and Password)
 * @param repository Name of the Artifactory repository to which the constructed url will direct to.
 * @return Full PyPI Url to the requested repository
 */
String createPypiUrl(String serverId, String credentialsId ,String repository){
    def serverUrl = createServerUrl(serverId, credentialsId)
    return "${serverUrl}/api/pypi/${repository}/simple"
}

/**
 * Constructs the Full Artifactory Url including the provided credentials
 *
 * @param serverId Artifactory server id that is defined in Jenkins (under Manage | Configure System)
 * @param credentialsId Jenkins defined Artifactory credentials ID (Username and Password)
 * @return Full Url to the requested Artifactory server
 */
String createServerUrl(String serverId, String credentialsId){
    def server = Artifactory.server serverId
    def url = server.getUrl()
    withCredentials([usernamePassword(credentialsId: credentialsId, passwordVariable: 'PASSWORD', usernameVariable: 'USERNAME')]) {
        def domain = (new URI(url)).getHost()
        // Add the username and password before the domain
        url = "${url.replace(domain, "${USERNAME}:${PASSWORD}@${domain}")}"
    }
    return url
}

/**
 * Convert the given object to a boolean if it has a value, else return the default value
 *
 * @param object The given object the will be converted to a boolean value
 * @param defaultValue The default boolean value to return in case the given object is empty (or null)
 * @return Boolean representation of the object if it has a value, else the given default value
 */
Boolean convertToBoolean(object, Boolean defaultValue){
    if(object == null) {
        return defaultValue;
    }
    return object.toBoolean();
}