def Jira_Issue__2_0_0__retrievewithwhere_Issue():
    return {}


def Jira_Project__2_0_0__retrievewithwhere_Project():
    return {}


def workflow():
    issues = set()
    projects = Jira_Project__2_0_0__retrievewithwhere_Project(where='name IS NOT NULL')
    for project in projects:
        subissues = Jira_Issue__2_0_0__retrievewithwhere_Issue(where=f"project = '{project['key']}'")
        issues['update']((subissue['key'] for subissue in subissues))
    return list(issues)
