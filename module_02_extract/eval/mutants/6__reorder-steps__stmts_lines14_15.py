def Slack_message__3_0_0__create_message():
    return {}

def Box_Folder__3_0_0__create_Folder():
    return {}

def user_task(label=None):
    return {'label': label}

def workflow():
    message = Slack_message__3_0_0__create_message()
    folder = Box_Folder__3_0_0__create_Folder()
    task = user_task('check team status')
    return None
