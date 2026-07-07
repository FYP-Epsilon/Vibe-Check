def Salesforce_CaseHistory__7_0_0__retrievewithwhere_CaseHistory():
    return {}


def Salesforce_CaseComment__7_0_0__create_CaseComment():
    return {}


def workflow():
    case_history = Salesforce_CaseHistory__7_0_0__retrievewithwhere_CaseHistory()
    if 'comments' in case_history:
        for comment in case_history['comments']:
            if 'isUpdatedComment' not in comment or not comment['isUpdatedComment']:
                if 'isCaseUpdated' not in comment or not comment['isCaseUpdated']:
                    new_comment = Salesforce_CaseComment__7_0_0__create_CaseComment(comment['body'])
