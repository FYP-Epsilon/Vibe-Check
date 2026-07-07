def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def GitLab_Project__5_0_0__create_Project():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    project = GitLab_Project__5_0_0__create_Project()
    user_task(label='Created new GitLab project: ' + project['get']('name'))
    Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
    user_task(label='Sent message to manager')
