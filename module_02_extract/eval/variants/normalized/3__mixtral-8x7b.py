def Box_Folder__3_0_0__create_Folder(folder_name: str = None):
    return {"name": folder_name}


def Salesforce_Contact__5_0_0__create_Contact():
    return {}


def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def workflow(folder_name: str):
    contact = Salesforce_Contact__5_0_0__create_Contact()
    Box_Folder__3_0_0__create_Folder(contact['Name'] + "'s Folder" if folder_name is None else folder_name)
    if folder_name is None:
        Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages(contact['Email'], 'New Folder Created!', f"Hello {contact['Name']},\n\nA new Box folder has been created for you.\n\nBest,\nThe Box Team")
