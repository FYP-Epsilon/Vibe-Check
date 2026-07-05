def Microsoft_OneDrive_for_Business_FolderItem__4_0_0__retrievewithwhere_FolderItem(folder_items_itemType_0: str=None, folder_items_itemType_1: str=None):
    return [{'itemType': folder_items_itemType_0}, {'itemType': folder_items_itemType_1}]

def Box_File__3_0_0__COPYFILE_File():
    return {}

def Microsoft_OneDrive_for_Business_Folder__4_0_0__retrievewithwhere_Folder():
    return {}

def Box_Folder__3_0_0__create_Folder():
    return {}

def workflow(folder_items_itemType_0: str, folder_items_itemType_1: str):
    folder = Microsoft_OneDrive_for_Business_Folder__4_0_0__retrievewithwhere_Folder()
    folder_items = Microsoft_OneDrive_for_Business_FolderItem__4_0_0__retrievewithwhere_FolderItem(folder_items_itemType_0=folder_items_itemType_0, folder_items_itemType_1=folder_items_itemType_1)
    new_folder = Box_Folder__3_0_0__create_Folder()
    for item in folder_items:
        if item['itemType'] != 'confidential':
            file = Box_File__3_0_0__COPYFILE_File()
    return None
    return None
