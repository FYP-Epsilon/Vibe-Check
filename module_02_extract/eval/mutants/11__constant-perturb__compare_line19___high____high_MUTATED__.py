def ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_priority: str=None):
    return {'priority': incident_priority}

def GitHub_Issue__3_0_0__create_Issue():
    return {}

def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}

def Jira_Issue__2_0_0__create_Issue():
    return {}

def workflow(incident_priority: str):
    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident(incident_priority=incident_priority)
    if incident['priority'] == 'high_MUTATED':
        issue = Jira_Issue__2_0_0__create_Issue()
        email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
    else:
        issue = GitHub_Issue__3_0_0__create_Issue()
    return None
