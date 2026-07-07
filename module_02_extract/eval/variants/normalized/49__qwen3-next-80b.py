def Jira_Project__2_0_0__retrievewithwhere_Project():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    project_data = Jira_Project__2_0_0__retrievewithwhere_Project()
    user_task(label='Copy project to Corpora')
    return project_data
