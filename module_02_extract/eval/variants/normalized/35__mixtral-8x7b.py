def Microsoft_Power_BI_Workspace__2_0_0__retrievewithwhere_Workspace():
    return {}


def Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal():
    return {}


def Microsoft_Power_BI_Scorecard__2_0_0__retrievewithwhere_Scorecard():
    return {}


def workflow():
    workspaces = Microsoft_Power_BI_Workspace__2_0_0__retrievewithwhere_Workspace()
    for workspace in workspaces['value']:
        workspace_id = workspace['id']
        scorecards = Microsoft_Power_BI_Scorecard__2_0_0__retrievewithwhere_Scorecard(workspace_id)
        for scorecard in scorecards['value']:
            scorecard_id = scorecard['id']
            goals = Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal(scorecard_id)
            for goal in goals['value']:
                print(f"Workspace: {workspace['name']}, Scorecard: {scorecard['name']}, Goal: {goal['displayName']}")
