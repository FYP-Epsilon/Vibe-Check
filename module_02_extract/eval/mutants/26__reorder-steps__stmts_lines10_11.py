def Salesforce_Lead__5_0_0__retrievewithwhere_Lead():
    return [{'value': 0}, {'value': 1}]

def Gmail_mail__2_0_0__create_mail():
    return {}

def workflow():
    for lead in leads:
        message = Gmail_mail__2_0_0__create_mail()
    leads = Salesforce_Lead__5_0_0__retrievewithwhere_Lead()
    return None
