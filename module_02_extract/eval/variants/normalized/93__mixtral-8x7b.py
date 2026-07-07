def Salesforce_UserRole__8_0_0__retrievewithwhere_UserRole(roles_name_0: str = None, roles_name_1: str = None):
    return [{"name": roles_name_0}, {"name": roles_name_1}]


def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def Salesforce_UserRole__8_0_0__updatewithwhere_UserRole():
    return {}


def workflow(roles_name_0: str, roles_name_1: str):
    user_roles = Salesforce_UserRole__8_0_0__retrievewithwhere_UserRole(roles_name_0, roles_name_1)
    for user_role in user_roles:
        if user_role['IsActive'] == False:
            continue
        Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages(user_role)
        Salesforce_UserRole__8_0_0__updatewithwhere_UserRole(user_role['Id'], user_role)
