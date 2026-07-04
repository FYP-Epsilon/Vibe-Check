def ServiceNow_sys_user__5_0_0__retrievewithwhere_sys_user():
    return {}


def ServiceNow_ticket__5_0_0__retrievewithwhere_ticket():
    return {}


def workflow():
    tickets = ServiceNow_ticket__5_0_0__retrievewithwhere_ticket()
    users = ServiceNow_sys_user__5_0_0__retrievewithwhere_sys_user()
    return None
