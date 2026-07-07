def Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model():
    return {}


def Asana_Tasks__2_0_0__retrievewithwhere_Tasks():
    return {}


def Slack_message__3_0_0__create_message():
    return {}


def workflow():
    tasks = Asana_Tasks__2_0_0__retrievewithwhere_Tasks()
    message = 'Available tasks: ' + ', '['join']([task['name'] for task in tasks])
    Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model(message)
    Slack_message__3_0_0__create_message(message, 'Available tasks')
