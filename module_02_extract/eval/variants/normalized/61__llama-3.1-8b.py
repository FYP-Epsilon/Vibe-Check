def Microsoft_Power_BI_Dataset__2_0_0__retrievewithwhere_Dataset():
    return {}


def Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal():
    return {}


def Microsoft_Power_BI_Workspace__2_0_0__create_Workspace():
    return {}


def Microsoft_Power_BI_Dataflow__2_0_0__retrievewithwhere_Dataflow():
    return {}


def workflow():
    dataflows = Microsoft_Power_BI_Dataflow__2_0_0__retrievewithwhere_Dataflow()
    datasets = Microsoft_Power_BI_Dataset__2_0_0__retrievewithwhere_Dataset()
    goals = Microsoft_Power_BI_Goal__2_0_0__retrievewithwhere_Goal()
    new_workspace = Microsoft_Power_BI_Workspace__2_0_0__create_Workspace()
    print('Dataflows:')
    for dataflow in dataflows:
        print(dataflow)
    print('Datasets:')
    for dataset in datasets:
        print(dataset)
    print('Goals:')
    for goal in goals:
        print(goal)
    return new_workspace
