def ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_impact: str=None):
    return {'impact': incident_impact}

def Slack_message__3_0_0__create_message():
    return {}

def GitHub_Issue__3_0_0__create_Issue():
    return {}

def Jira_Issue__2_0_0__create_Issue():
    return {}

def workflow(incident_impact: str):
    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_impact=incident_impact)
    if issue['impact'] == 'high':
        issue = Jira_Issue__2_0_0__create_Issue()
        message = Slack_message__3_0_0__create_message()
    else:
        issue = GitHub_Issue__3_0_0__create_Issue()
    return None
