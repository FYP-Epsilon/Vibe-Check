def Jira_Issue__2_0_0__retrievewithwhere_Issue(issues_priority_0: str = None, issues_priority_1: str = None):
    return [{"priority": issues_priority_0}, {"priority": issues_priority_1}]


def Asana_Tasks__2_0_0__create_Tasks():
    return {}


def Gmail_mail__2_0_0__create_mail():
    return {}


def Slack_message__3_0_0__create_message():
    return {}


def workflow(issues_priority_0: str, issues_priority_1: str):
    issues = Jira_Issue__2_0_0__retrievewithwhere_Issue(issues_priority_0, issues_priority_1)
    for issue in issues:
        if issue['priority'] == 'urgent':
            Asana_Tasks__2_0_0__create_Tasks()
            recipients = [user['email'] for user in issue['assignees']]
            mail = Gmail_mail__2_0_0__create_mail(issue['subject'], issue['description'], recipients)
            mail['send']()
        elif issue['priority'] == 'low':
            message = Slack_message__3_0_0__create_message(issue['subject'], issue['description'])
            message['send_to'](channel='general')
