def Box_Folder__3_0_0__retrievewithwhere_Folder(folders_is_collaboration_restricted_to_enterprise_0: str = None, folders_is_collaboration_restricted_to_enterprise_1: str = None):
    return [{"is_collaboration_restricted_to_enterprise": folders_is_collaboration_restricted_to_enterprise_0}, {"is_collaboration_restricted_to_enterprise": folders_is_collaboration_restricted_to_enterprise_1}]


def Box_Folder__3_0_0__COPYFOLDER_Folder():
    return {}


def Box_Folder__3_0_0__updatewithwhere_Folder():
    return {}


def workflow(folders_is_collaboration_restricted_to_enterprise_0: str, folders_is_collaboration_restricted_to_enterprise_1: str):
    folders = Box_Folder__3_0_0__retrievewithwhere_Folder(folders_is_collaboration_restricted_to_enterprise_0=folders_is_collaboration_restricted_to_enterprise_0, folders_is_collaboration_restricted_to_enterprise_1=folders_is_collaboration_restricted_to_enterprise_1)
    for folder in folders:
        if folder['is_collaboration_restricted_to_enterprise'] == false:
            new_folder = Box_Folder__3_0_0__COPYFOLDER_Folder()
        else:
            folder = Box_Folder__3_0_0__updatewithwhere_Folder()
    return None
