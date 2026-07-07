def Slack_im__3_0_0__retrievewithwhere_im(dms_messages_0: str = None, dms_messages_1: str = None):
    return [{"messages": dms_messages_0}, {"messages": dms_messages_1}]


def user_task(label=None):
    return {'label': label}


def workflow(dms_messages_0: str, dms_messages_1: str):
    search_term = '401k'
    result = Slack_im__3_0_0__retrievewithwhere_im(dms_messages_0=dms_messages_0, dms_messages_1=dms_messages_1)
    if result:
        return user_task(label="Slack DMs containing '{}'"['format'](search_term), content=result)
    else:
        return user_task(label="No Slack DMs containing '{}' found"['format'](search_term))
