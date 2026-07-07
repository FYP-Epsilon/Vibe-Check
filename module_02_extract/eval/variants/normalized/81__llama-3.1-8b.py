def ServiceNow_kb_knowledge__5_0_0__create_kb_knowledge():
    return {}


def Dropbox_files__3_0_0__create_files():
    return {}


def workflow():
    Dropbox_files__3_0_0__create_files()
    print('Replacing Box with Dropbox')
    ServiceNow_kb_knowledge__5_0_0__create_kb_knowledge()
    print('Box replaced with Dropbox successfully')
