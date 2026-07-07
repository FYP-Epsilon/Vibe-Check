def Microsoft_OneDrive_for_Business_FolderItem__4_0_0__retrievewithwhere_FolderItem(folder_items_itemType_0: str = None, folder_items_itemType_1: str = None):
    return [{"itemType": folder_items_itemType_0}, {"itemType": folder_items_itemType_1}]


def Box_File__3_0_0__COPYFILE_File():
    return {}


def Microsoft_OneDrive_for_Business_Folder__4_0_0__retrievewithwhere_Folder():
    return {}


def Box_Folder__3_0_0__create_Folder():
    return {}


def workflow(folder_items_itemType_0: str, folder_items_itemType_1: str):
    if folder_items_itemType_0 == 'confidential':
        print('File type is confidential, skipping copy')
    else:
        Box_File__3_0_0__COPYFILE_File()
