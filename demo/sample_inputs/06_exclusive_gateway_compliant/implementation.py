def ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_priority: str = 'high'):
    return {"priority": incident_priority}


def Jira_Issue__2_0_0__create_Issue():
    return {"id": "JIRA-101"}


def Slack_message__3_0_0__create_message():
    return {"status": "sent"}


def GitHub_Issue__3_0_0__create_Issue():
    return {"id": "GH-202"}


def workflow(incident_priority: str = 'high'):
    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_priority)
    if incident.get("priority") == 'high':
        jira = Jira_Issue__2_0_0__create_Issue()
        slack = Slack_message__3_0_0__create_message()
    else:
        gh = GitHub_Issue__3_0_0__create_Issue()
