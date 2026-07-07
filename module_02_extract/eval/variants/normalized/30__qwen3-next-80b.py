def Box_File__3_0_0__retrievewithwhere_File(files_owned_by_0: str = None, files_owned_by_1: str = None):
    return [{"owned_by": files_owned_by_0}, {"owned_by": files_owned_by_1}]


def Box_File__3_0_0__deletewithwhere_File():
    return {}


def Jira_Issue__2_0_0__create_Issue():
    return {}


def workflow(files_owned_by_0: str, files_owned_by_1: str):
    files = Box_File__3_0_0__retrievewithwhere_File(files_owned_by_0, files_owned_by_1)
    Box_File__3_0_0__deletewithwhere_File()
    Jira_Issue__2_0_0__create_Issue()
