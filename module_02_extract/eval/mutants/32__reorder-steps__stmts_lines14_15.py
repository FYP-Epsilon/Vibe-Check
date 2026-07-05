def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}

def GitLab_Project__5_0_0__create_Project():
    return {}

def user_task(label=None):
    return {'label': label}

def workflow():
    message = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
    project = GitLab_Project__5_0_0__create_Project()
    task = user_task('check with manager')
    return None
