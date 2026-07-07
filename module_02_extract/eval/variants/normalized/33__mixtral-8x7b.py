def ServiceNow_sys_user__5_0_0__retrievewithwhere_sys_user():
    return {}


def ServiceNow_ticket__5_0_0__retrievewithwhere_ticket():
    return {}


def workflow():
    tickets = ServiceNow_ticket__5_0_0__retrievewithwhere_ticket(where='active=true')
    users = ServiceNow_sys_user__5_0_0__retrievewithwhere_sys_user(where='active=true')
    ticket_data = [ticket['to_dict']() for ticket in tickets]
    user_data = [user['to_dict']() for user in users]
    result = {'tickets': ticket_data, 'users': user_data}
    return result
