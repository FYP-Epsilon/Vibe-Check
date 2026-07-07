def Slack_channel__3_0_0__retrievewithwhere_channel():
    return [{'value': 0}, {'value': 1}]


def Slack_user__4_0_0__retrievewithwhere_user():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    channels = Slack_channel__3_0_0__retrievewithwhere_channel()
    for channel in channels:
        users = Slack_user__4_0_0__retrievewithwhere_user()
        for user in users:
            user_task(label=f"Validating credentials for user {user['id']} in channel {channel['id']}")
