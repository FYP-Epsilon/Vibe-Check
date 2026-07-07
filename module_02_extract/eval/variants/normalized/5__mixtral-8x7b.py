def Salesforce_Account__5_0_0__retrievewithwhere_Account():
    return [{'value': 0}, {'value': 1}]


def Box_File__3_0_0__create_File():
    return {}


def Box_Folder__3_0_0__create_Folder():
    return {}


def workflow():
    sf_accounts = Salesforce_Account__5_0_0__retrievewithwhere_Account()
    box_folder = Box_Folder__3_0_0__create_Folder('Salesforce Accounts')
    for sf_account in sf_accounts:
        Box_File__3_0_0__create_File(box_folder, sf_account['Name'], sf_account)
