def monday_com_User__2_0_0__retrievewithwhere_User():
    return [{'value': 0}, {'value': 1}]


def Box_Folder__3_0_0__retrievewithwhere_Folder():
    return [{'value': 0}, {'value': 1}]


def Box_Folder__3_0_0__deletewithwhere_Folder():
    return {}


def workflow():
    users = monday_com_User__2_0_0__retrievewithwhere_User()
    folder_ids_to_delete = []
    for user in users:
        user_folders = Box_Folder__3_0_0__retrievewithwhere_Folder(user_id=user['id'])
        folder_ids_to_delete['extend']([folder['id'] for folder in user_folders])
    for folder_id in folder_ids_to_delete:
        Box_Folder__3_0_0__deletewithwhere_Folder(folder_id=folder_id)
