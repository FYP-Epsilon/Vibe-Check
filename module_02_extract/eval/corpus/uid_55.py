def Marketo_leads__3_0_0__retrievewithwhere_leads():
    return [{'value': 0}, {'value': 1}]


def Salesforce_Lead__5_0_0__create_Lead():
    return {}


def workflow():
    leads = Marketo_leads__3_0_0__retrievewithwhere_leads()
    for lead in leads:
        lead = Salesforce_Lead__5_0_0__create_Lead()
    return None
