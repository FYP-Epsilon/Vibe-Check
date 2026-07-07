def Marketo_leads__3_0_0__retrievewithwhere_leads():
    return [{'value': 0}, {'value': 1}]


def Microsoft_Teams_Message__2_0_0__create_Message():
    return {}


def Salesforce_Lead__5_0_0__create_Lead():
    return {}


def workflow():
    lead = Salesforce_Lead__5_0_0__create_Lead()
    leads = Marketo_leads__3_0_0__retrievewithwhere_leads()
    if lead in leads:
        message = Microsoft_Teams_Message__2_0_0__create_Message()
        print('Message sent to Microsoft Teams')
