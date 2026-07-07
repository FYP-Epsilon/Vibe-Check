def Asana_Tasks__2_0_0__retrievewithwhere_Tasks():
    return [{'value': 0}, {'value': 1}]


def Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model():
    return {}


def workflow():
    tasks = Asana_Tasks__2_0_0__retrievewithwhere_Tasks()
    for task in tasks:
        message = f"Task {task['name']} is due on {task['due_date']}"
        Twilio_postMessagesjsonByFromphone_model__2_0_0__postMessagesjsonByFromphone_postMessagesjsonByFromphone_model(from_phone_number=task['assignee']['phone_number'], to_phone_number=task['assignee']['phone_number'], message=message)
