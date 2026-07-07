def Salesforce_Lead__5_0_0__retrievewithwhere_Lead():
    return [{'value': 0}, {'value': 1}]


def Gmail_mail__2_0_0__create_mail():
    return {}


def workflow():
    leads = Salesforce_Lead__5_0_0__retrievewithwhere_Lead()
    for lead in leads:
        status_message = 'New lead from Salesforce: ' + str(lead)
        mail = Gmail_mail__2_0_0__create_mail()
        mail['set_subject']('New Lead')
        mail['set_body'](status_message)
        mail['send']()
