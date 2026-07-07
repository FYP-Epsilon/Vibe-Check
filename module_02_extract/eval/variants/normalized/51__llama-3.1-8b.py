def Microsoft_Dynamics_365_for_Finance_and_Operations_Applicant__2_0_0__create_Applicant():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    user_task(label='Start new application')
    user_task(label='Create applicant')
    Microsoft_Dynamics_365_for_Finance_and_Operations_Applicant__2_0_0__create_Applicant()
