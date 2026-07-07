def Trello_Organization__2_0_0__retrievewithwhere_Organization(teams_type_0: str = None, teams_type_1: str = None):
    return [{"type": teams_type_0}, {"type": teams_type_1}]


def Marketo_leads__3_0_0__create_leads():
    return {}


def workflow(teams_type_0: str, teams_type_1: str):
    teams = Trello_Organization__2_0_0__retrievewithwhere_Organization(teams_type_0, teams_type_1)
    for team in teams:
        if team['get']('type') == 'customer':
            Marketo_leads__3_0_0__create_leads(firstName=team['get']('name', ''), lastName='', email='', organization=team['get']('name', ''), source='Trello Team')
