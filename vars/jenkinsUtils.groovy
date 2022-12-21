/**
 * Clear the jenkins build queue (Clear the entire queue, or just jobs that match the given pattern).
 * @param pattern All jobs that match this given regular expression pattern will be cleared from the queue.
 * Example for the regular expression: ([Gg])roovy , .*Staging.* ,^Builder.*Production$
 */
@NonCPS
def clearBuildQueue(String pattern = ''){
    def queue = Jenkins.instance.queue
    if(pattern) {
        queue.items.findAll { it.task.name =~ pattern}.each {
            println "Item '${it.task.name}' was cleared from the queue"
            queue.cancel(it.task)
        }
    }
    else {
        println "Clearing ${queue.items.length} items from the queue"
        queue.clear()
    }
}

/**
 * Remove a specific node from the Jenkins server.
 * Attention: <strong>Node will be permanently deleted.</strong>
 * @param nodeName Name of the node to remove.
 * @param failIfNotFound Throw an exception if the node is not found.
 * @return True if node was found and deleted, false if the node is not found and the 'failIfNotFound' flag is false.
 */
@NonCPS
def removeNode(String nodeName, Boolean failIfNotFound = false) {
    assert nodeName : "The node name parameter cannot be empty"
    println "Removing node '${nodeName}' from the Jenkins server"
    def machineNode = Jenkins.instance.nodes.find { it.name == nodeName }
    if (machineNode) {
        Jenkins.instance.removeNode(machineNode)
        println "Node '${nodeName}' was removed sucssefully"
        return true
    }
    def notFoundMessage = "A Node matching the name '${nodeName}' was not found"
    failIfNotFound ? error(notFoundMessage) : println(notFoundMessage)
    return false
}

/**
 * Cancel all previous builds of the job.
 * Only builds that are <strong>ongoing (currently running) and older than the current build</strong> will be canceled.
 * All canceled builds will receive a user like stop command (interrupted signal) and will appear as Aborted.
 */
@NonCPS
def cancelPreviousBuilds() {
    int currentBuildNum = env.BUILD_NUMBER.toInteger()

    def job = Jenkins.instance.getItemByFullName(env.JOB_NAME)
    for (build in job.builds) {
        // Only cancel builds that are ongoing and older than the current build
        if (build.isBuilding() && currentBuildNum > build.getNumber().toInteger()) {
            build.doStop();
            println "Build '${build.toString()}' was cancelled"
        }
    }
}

/**
 * Delete all non-running builds of the given job (or the current one if left empty).
 * @param fullJobName The full name of the Job (project) for which to delete all the builds.
 * If left empty, builds from the <strong>current running job</strong> will be deleted.
 * When using view Folder full names are like path names, where each name of Item is combined by '/'.
 * For example: job 'Build' under the folder 'Production' - full name will be 'Production/Build'
 */
@NonCPS
def deleteAllBuilds(String fullJobName ='') {
    def jobName = fullJobName ?: env.JOB_NAME
    println "Deleting all the builds for job '${jobName}'"

    // Get all builds
    def builds = Jenkins.instance.getItemByFullName(jobName).builds
    if(builds) {
        // Only delete builds that are not running
        builds.findAll { !it.isBuilding() }.each { build ->
            build.delete();
            println "Build '${build.toString()}' was deleted"
        }
    }
    else {
        error "A job matching the name '${nodeName}' was not found. Have you used the Full Job Name?"
    }
}

/**
 * Add a side bar link (action) to the running job, at the build level or at the job (project) level.
 * Attention: <strong>Requires that the sidebar-link plugin (https://plugins.jenkins.io/sidebar-link/) will be installed on Jenkins server</strong>
 * @param url The URL that the link will be pointing to (Must be accessible from the Jenkins server).
 * @param displayName The display name of the link that will appear in the side menu of the build\job.
 * @param relativeIconPath The relative icon path that will be displayed in the link. If empty no icon will be used.
 * Example: images/48x48/jira.png, images/32x32/attribute.png. (Image must exists in the war/images folder on the Jenkins server)
 * @param linkToBuild True (Default) - Add the link to the build level. False - Add the link to the Job level.
 */
def addJobSideBarLink(String url, String displayName, String relativeIconPath, Boolean linkToBuild = true) {
    assert url : "The URL parameter cannot be empty"
    assert displayName : "The Display Name parameter cannot be empty"
    try {
        def linkActionClass = this.class.classLoader.loadClass("hudson.plugins.sidebar_link.LinkAction")
        def run = linkToBuild ? currentBuild.rawBuild : currentBuild.rawBuild.getParent()
        def action = linkActionClass.newInstance(url, displayName, relativeIconPath)
        println "Adding to the ${linkToBuild ? 'build' : 'job'} level a sidebar link to '${action.getUrlName()}' with name '${action.getDisplayName()}' and icon '${action.getIconFileName()}'"
        run.getActions().add(action)
    } catch (Exception e) {
        println "Failed to add side bar link: ${e.toString()}"
    }
}

/**
 * Remove a side bar link (action) from the running job, at the build level or at the job (project) level.
 * Attention: <strong>Requires that the sidebar-link plugin (https://plugins.jenkins.io/sidebar-link/) will be installed on Jenkins server</strong>
 * @param displayName The display name of the link that will be removed from the side menu of the build\job.
 * @param removeFromBuild True (Default) - Remove the link from the build level. False - Remove the link from the Job level.
 */
def removeJobSideBarLink(String displayName, Boolean removeFromBuild = true) {
    assert displayName : "The Display Name parameter cannot be empty"
    try {
        def linkActionClass = this.class.classLoader.loadClass("hudson.plugins.sidebar_link.LinkAction")
        def run = removeFromBuild ? currentBuild.rawBuild : currentBuild.rawBuild.getParent()
        for (action in run.getActions()) {
            if(linkActionClass.isAssignableFrom(action.getClass()) && action.getDisplayName() == displayName) {
                println "Removing from the ${removeFromBuild ? 'build' : 'job'} level the sidebar link to '${action.getUrlName()}' with name '${action.getDisplayName()}' and icon '${action.getIconFileName()}'"
                run.getActions().remove(action)
            }
        }
    } catch (Exception e) {
        println "Failed to remove side bar link: ${e.toString()}"
    }
}

/**
 * Get the last upstream build that triggered the current build
 * @return Build object (org.jenkinsci.plugins.workflow.job.WorkflowRun) representing the upstream build
 */
@NonCPS
def getUpstreamBuild() {
    def build = currentBuild.rawBuild
    def upstreamCause
    while (upstreamCause = build.getCause(hudson.model.Cause$UpstreamCause)) {
        build = upstreamCause.upstreamRun
    }
    return build
}

/**
 * Get the properties of the build Cause (the event that triggered the build)
 * @param upstream If true (Default) return the cause properties of the last upstream job (If the build was triggered by another job or by a chain of jobs)
 * @return Map representing the properties of the cause that triggered the current build.
 */
@NonCPS
def getCauseProperties(Boolean upstream = true) {
    def build = upstream ? getUpstreamBuild() : currentBuild.rawBuild
    return build.getCauses()[0].properties
}

/**
 * Get the description of the build Cause (the event that triggered the build)
 * @param upstream If true (Default) return the cause properties of the last upstream job (If the build was triggered by another job or by a chain of jobs)
 * @return String representing the description of the cause that triggered the current build.
 */
@NonCPS
def getCauseDescription(Boolean upstream = true) {
    return getCauseProperties(upstream).shortDescription
}

/**
 * Get the User Name that has triggered the current build
 * @param upstream If true (Default) return the User Name that triggered the last upstream job (If the build was triggered by another job or by a chain of jobs)
 * @return String representing the User Name that triggered the build or an empty string if the build was not started by a user.
 */
@NonCPS
def getBuildUserName(Boolean upstream = true) {
    def build = upstream ? getUpstreamBuild() : currentBuild.rawBuild
    def userIdCause = build.getCause(hudson.model.Cause$UserIdCause)
    if(userIdCause) {
        return userIdCause.userName
    }
    println "Job was not started by a user, it was ${build.getCauses()[0].shortDescription}"
    return ''
}
