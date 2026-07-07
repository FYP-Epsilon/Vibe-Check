def Salesforce_Account__5_0_0__create_Account():
    return {}


def Salesforce_Case__5_0_0__create_Case():
    return {}


def Salesforce_Asset__8_0_0__create_Asset():
    return {}


def workflow():
    account_result = Salesforce_Account__5_0_0__create_Account()
    case_result = Salesforce_Case__5_0_0__create_Case()
    asset_result = Salesforce_Asset__8_0_0__create_Asset(account_result['id'])
    return {'account': account_result, 'case': case_result, 'asset': asset_result}
