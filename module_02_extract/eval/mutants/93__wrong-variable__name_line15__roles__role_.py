def Salesforce_UserRole__8_0_0__retrievewithwhere_UserRole(roles_name_0: str=None, roles_name_1: str=None):
    return [{'name': roles_name_0}, {'name': roles_name_1}]

def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}

def Salesforce_UserRole__8_0_0__updatewithwhere_UserRole():
    return {}

def workflow(roles_name_0: str, roles_name_1: str):
    roles = Salesforce_UserRole__8_0_0__retrievewithwhere_UserRole(roles_name_0=roles_name_0, roles_name_1=roles_name_1)
    for role in role:
        if role['name'] != 'inactive':
            update_user = Salesforce_UserRole__8_0_0__updatewithwhere_UserRole()
            email_user = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
    return None
