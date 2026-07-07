def Jira_Issue__2_0_0__retrievewithwhere_Issue(issues_fields_0: str = None, issues_fields_1: str = None):
    return [{"fields": issues_fields_0}, {"fields": issues_fields_1}]


def Asana_Tasks__2_0_0__create_Tasks():
    return {}


def Gmail_mail__2_0_0__create_mail():
    return {}


def Asana_Attachments__2_0_0__create_Attachments():
    return {}


def Slack_message__3_0_0__create_message():
    return {}


def workflow(issues_fields_0: str, issues_fields_1: str):
    tasks = Asana_Tasks__2_0_0__create_Tasks()
    for task in tasks:
        Asana_Attachments__2_0_0__create_Attachments(task['id'])
        print(task)
