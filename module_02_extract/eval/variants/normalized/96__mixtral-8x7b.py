def Box_Folder__3_0_0__retrievewithwhere_Folder(folders_is_collaboration_restricted_to_enterprise_0: str = None, folders_is_collaboration_restricted_to_enterprise_1: str = None):
    return [{"is_collaboration_restricted_to_enterprise": folders_is_collaboration_restricted_to_enterprise_0}, {"is_collaboration_restricted_to_enterprise": folders_is_collaboration_restricted_to_enterprise_1}]


def Box_Folder__3_0_0__COPYFOLDER_Folder():
    return {}


def Box_Folder__3_0_0__updatewithwhere_Folder():
    return {}


def workflow(folders_is_collaboration_restricted_to_enterprise_0: str, folders_is_collaboration_restricted_to_enterprise_1: str):
    if folders_is_collaboration_restricted_to_enterprise_0 or folders_is_collaboration_restricted_to_enterprise_1:
        copied_folder = Box_Folder__3_0_0__COPYFOLDER_Folder()
        Box_Folder__3_0_0__updatewithwhere_Folder(copied_folder, is_collaboration_restricted_to_enterprise=False)
        return copied_folder
    else:
        return None
