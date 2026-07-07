def ServiceNow_incident__4_0_0__retrievewithwhere_incident():
    return {}


def Zendesk_Service_Ticket__2_0_0__create_Ticket():
    return {}


def Zendesk_Service_ticketAttachment__2_0_0__UPLOADATTACHMENT_ticketAttachment():
    return {}


def workflow():
    incident = ServiceNow_incident__4_0_0__retrievewithwhere_incident()
    if incident:
        ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket(incident)
        if ticket and incident['get']('attachement'):
            Zendesk_Service_ticketAttachment__2_0_0__UPLOADATTACHMENT_ticketAttachment(ticket, incident['get']('attachement'))
    else:
        print('No incident found')
