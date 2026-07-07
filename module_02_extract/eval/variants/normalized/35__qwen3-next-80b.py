def Microsoft_Power_BI_Workspace__2_0_0__retrievewithwhere_Workspace():
    return {}


def Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal():
    return {}


def Microsoft_Power_BI_Scorecard__2_0_0__retrievewithwhere_Scorecard():
    return {}


def workflow():
    workspaces = Microsoft_Power_BI_Workspace__2_0_0__retrievewithwhere_Workspace()
    scorecards = Microsoft_Power_BI_Scorecard__2_0_0__retrievewithwhere_Scorecard()
    goals = Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal()
    return {'workspaces': workspaces, 'scorecards': scorecards, 'goals': goals}
