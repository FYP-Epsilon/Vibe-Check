def Jira_Project__2_0_0__retrievewithwhere_Project():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    project = Jira_Project__2_0_0__retrievewithwhere_Project()
    task = user_task('Copy project to Corpora')
    return None
