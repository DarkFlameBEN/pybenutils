// Git Utilities
// Attention: <strong>All functions should be called from within a cloned git repository folder</strong>

/**
 * Set the git user configuration (name and mail)
 * @param userName Git username
 * @param userEmail Git user Email
 */
def setUserConfig(String userName, String userEmail) {
    cmd "git config --global user.email '${userEmail}'"
    cmd "git config --global user.name '${userName}'"
}

/**
 * Download commits, files, and refs (branches and/or tags) from a remote repository into your local repo
 * @param credentialsId Git credentials id defined in the Jenkins master (used via ssh agent)
 * @param repository Remote repository to fetch from. Default value is 'origin' (original cloned from repository)
 */
def fetch(String credentialsId, String repository = 'origin') {
    assert credentialsId : "Credentials Id cannot be empty"
    sshagent([credentialsId]) {
        cmd "git fetch ${repository}"
    }
}

/**
 * Fetch and download content from a remote repository and immediately update the local repository to match that content
 * @param credentialsId Git credentials id defined in the Jenkins master (used via ssh agent)
 * @param repository Remote repository to pull from. Default value is 'origin' (original cloned from repository)
 */
def pull(String credentialsId, String repository = 'origin') {
    assert credentialsId : "Credentials Id cannot be empty"
    sshagent([credentialsId]) {
        cmd "git pull ${repository}"
    }
}

/**
 * Capture a snapshot of the project's currently staged changes (record changes to the repository)
 * Changes from all known files (i.e. all files that are already listed in the index) will be automatically added
 * @param message The message that will be associated with these changes
 */
def commit(String message) {
    assert message : 'The commit message cannot be empty'
    cmd "git commit -a -m \"${message}\""
}

/**
 * Upload local repository content to a remote repository (update remote refs along with associated objects)
 * <strong>The push command will be used with the --set-upstream (-u) flag to create a correlation with a corresponding remote branch</strong>
 * @param credentialsId Git credentials id defined in the Jenkins master (used via ssh agent)
 * @param branch Remote branch name that will be set as the remote tracking branch of the branch that is being pushed
 * @param repository Remote repository to pull from. Default value is 'origin' (original cloned from repository)
 * @param repository True for pushing locally created tags to the repository (Default - false)
 */
def push(String credentialsId, String branch, String repository = 'origin', Boolean pushTags = false) {
    assert credentialsId : "Credentials Id cannot be empty"
    sshagent([credentialsId]) {
        cmd "git push -u ${repository} ${branch}${pushTags ? ' --tags' : ''}"
    }
}

/**
 * Create a git annotated tag
 * @param tagName The name of the tag to create
 * @param message Optional annotation that will be associated with the tag
 */
def tag(String tagName, String message =''){
    assert tagName : "The tag name cannot be empty"
    cmd "git tag -a '${tagName}' -m '${message}'"
}

/**
 * Create a git annotated tag and push it to a remote repository
 * @param credentialsId Git credentials id defined in the Jenkins master (used via ssh agent)
 * @param tagName The name of the tag to create
 * @param message Optional annotation that will be associated with the tag
 * @param repository Remote repository to pull from. Default value is 'origin' (original cloned from repository)
 */
def pushTag(String credentialsId, String tagName, String message, String repository = 'origin') {
    assert credentialsId : "Credentials Id cannot be empty"
    tag(tagName, message)
    sshagent([credentialsId]) {
        cmd "git push origin ${tagName}"
    }
}

/**
 * Switch branches in the local repository
 * @param branch Branch name to switch to (branch must already exist in the repository)
 */
def checkout(String branch) {
    cmd "git checkout ${branch}"
}

/**
 * Reset current HEAD to the last specified state (last commit)
 * @param mode The reset mode, choose from the following:
 *    hard (Default) - Resets the index and working tree. Any changes to tracked files since last commit are discarded.
 *    soft - Does not touch the index file or the working tree at all (this leaves all your changed files "Changes to be committed")
 *    mixed - Resets the index but not the working tree (the changed files are preserved but not marked for commit)
 */
def reset(String mode = 'hard') {
    assert ['hard','mixed','soft'].containsValue(mode) : "Illegal mode value '${mode}'. Valid options: 'hard','mixed','soft'."
    cmd "git reset --${mode}"
}

/**
 * Show differences between your working directory and the index.
 * @return The git differences as string
 */
String diff() {
    return cmd(script: "git diff", returnStdout: true).trim()
}

/**
 * Get the latest commit message from the current git repository
 * Attention: <strong>This function should be called from within a pre-cloned git repository</strong>
 * @return The last commit message as string
 */
String getCommitMsg() {
    return cmd(script: "git log -n 1 --pretty=format:%s", returnStdout: true).trim()
}

/**
 * Get the date of the latest commit from the current git repository
 * Attention: <strong>This function should be called from within a pre-cloned git repository</strong>
 * @return The last commit date as string in the following format: %dd-%mm-%yy
 */
String getCommitDate() {
    return cmd(script: "git log -n 1 --date=format:%y-%m-%d --pretty=format:%cd", returnStdout: true).trim()
}