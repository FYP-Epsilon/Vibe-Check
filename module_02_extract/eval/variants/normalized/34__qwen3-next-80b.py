def Microsoft_SharePoint_Folder__204_0_0__create_Folder():
    return {}


def Microsoft_SharePoint_File__204_0_0__create_File():
    return {}


def workflow():
    folder_name = 'NewFolder'
    file_name = 'NewFile.txt'
    folder_path = Microsoft_SharePoint_Folder__204_0_0__create_Folder(folder_name)
    Microsoft_SharePoint_File__204_0_0__create_File(folder_path, file_name)
