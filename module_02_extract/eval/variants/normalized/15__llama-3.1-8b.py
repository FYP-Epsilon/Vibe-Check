def Trello_Organization__2_0_0__retrievewithwhere_Organization(teams_name_0: str = None, teams_name_1: str = None):
    return [{"name": teams_name_0}, {"name": teams_name_1}]


def Marketo_leads__3_0_0__create_leads():
    return {}


def Gmail_mail__2_0_0__create_mail():
    return {}


def workflow(teams_name_0: str, teams_name_1: str):
    if teams_name_0 == 'internal':
        Gmail_mail__2_0_0__create_mail()
