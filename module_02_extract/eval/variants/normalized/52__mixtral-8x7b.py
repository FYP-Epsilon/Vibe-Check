def Microsoft_OneDrive_for_Business_FolderItem__4_0_0__retrievewithwhere_FolderItem():
    return [{'value': 0}, {'value': 1}]


def Box_File__3_0_0__COPYFILE_File():
    return {}


def Microsoft_OneDrive_for_Business_Folder__4_0_0__retrievewithwhere_Folder():
    return {}


def Box_Folder__3_0_0__create_Folder():
    return {}


def workflow():
    one_drive_folder = Microsoft_OneDrive_for_Business_FolderItem__4_0_0__retrievewithwhere_FolderItem()
    box_folder = Box_Folder__3_0_0__create_Folder()
    for file_item in one_drive_folder['value']:
        if 'file' in file_item:
            file = file_item['file']
            Box_File__3_0_0__COPYFILE_File(box_folder['id'], file['name'], file['@microsoft.graph.downloadUrl'])
    return 'Files copied from OneDrive to Box'
