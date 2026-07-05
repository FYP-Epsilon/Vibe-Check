def GitHub_Comment__3_0_0__create_Comment():
    return {}

def GitHub_Pullrequest__3_0_0__create_Pullrequest():
    return {}

def GitHub_Issue__3_0_0__create_Issue():
    return {}

def Jira_Issue__2_0_0__create_Issue():
    return {}

def workflow():
    jira_op = Jira_Issue__2_0_0__create_Issue()
    issue = GitHub_Issue__3_0_0__create_Issue()
    pr = GitHub_Pullrequest__3_0_0__create_Pullrequest()
    return None
    comment = GitHub_Comment__3_0_0__create_Comment()
    return None
