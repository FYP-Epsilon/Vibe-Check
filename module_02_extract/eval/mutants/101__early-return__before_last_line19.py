def monday_com_User__2_0_0__retrievewithwhere_User():
    return [{'value': 0}, {'value': 1}]

def Box_Folder__3_0_0__retrievewithwhere_Folder():
    return [{'value': 0}, {'value': 1}]

def Box_Folder__3_0_0__deletewithwhere_Folder():
    return {}

def workflow():
    users = monday_com_User__2_0_0__retrievewithwhere_User()
    for user in users:
        folders = Box_Folder__3_0_0__retrievewithwhere_Folder()
        for folder in folders:
            del_folder = Box_Folder__3_0_0__deletewithwhere_Folder()
    return None
    return None
