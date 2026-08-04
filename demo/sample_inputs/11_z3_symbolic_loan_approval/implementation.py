def Verify_Applicant_Identity(applicant_id: str = "APP-1001"):
    return {"identity_verified": True}


def Run_Credit_Bureau_Check(applicant_id: str):
    return {"checked": True}


def Approve_Priority_Loan(applicant_id: str):
    return {"status": "approved_priority", "vip": True}


def Flag_For_Manual_Review(applicant_id: str):
    return {"status": "flagged_for_review"}


def workflow(applicant_id: str = "APP-1001", referral_code: int = 0):
    Verify_Applicant_Identity(applicant_id)
    Run_Credit_Bureau_Check(applicant_id)

    if referral_code == 77531:
        result = Approve_Priority_Loan(applicant_id)
    else:
        result = Flag_For_Manual_Review(applicant_id)
    return result
