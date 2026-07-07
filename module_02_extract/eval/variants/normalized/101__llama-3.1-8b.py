def monday_com_User__2_0_0__retrievewithwhere_User():
    return [{'value': 0}, {'value': 1}]


def Box_Folder__3_0_0__retrievewithwhere_Folder():
    return [{'value': 0}, {'value': 1}]


def Box_Folder__3_0_0__deletewithwhere_Folder():
    return {}


def workflow():
    users = monday_com_User__2_0_0__retrievewithwhere_User()
    user_ids = [user['id'] for user in users]
    box_folders = Box_Folder__3_0_0__retrievewithwhere_Folder()
    folder_ids = [folder['id'] for folder in box_folders if folder['user_id'] in user_ids]
    Box_Folder__3_0_0__deletewithwhere_Folder(folder_ids)
