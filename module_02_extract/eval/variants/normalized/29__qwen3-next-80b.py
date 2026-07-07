def Salesforce_Contact__5_0_0__create_Contact():
    return {}


def Gmail_mail__2_0_0__create_mail():
    return {}


def Box_File__3_0_0__create_File():
    return {}


def Box_Folder__3_0_0__create_Folder():
    return {}


def workflow():
    contact_id = Salesforce_Contact__5_0_0__create_Contact()
    folder_id = Box_Folder__3_0_0__create_Folder()
    file_id = Box_File__3_0_0__create_File(folder_id)
    Gmail_mail__2_0_0__create_mail()
    return None
