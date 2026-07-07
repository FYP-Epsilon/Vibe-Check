def Asana_Tasks__2_0_0__retrievewithwhere_Tasks():
    return [{'value': 0}, {'value': 1}]


def Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model():
    return {}


def workflow():
    tasks = Asana_Tasks__2_0_0__retrievewithwhere_Tasks()
    for task in tasks:
        Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model(body=f"New task: {task['get']('name', 'Unnamed Task')}")
