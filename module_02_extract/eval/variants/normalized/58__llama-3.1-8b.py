def ServiceNow_incident__4_0_0__retrievewithwhere_incident():
    return {}


def Zendesk_Service_Ticket__2_0_0__create_Ticket():
    return {}


def Zendesk_Service_ticketAttachment__2_0_0__UPLOADATTACHMENT_ticketAttachment():
    return {}


def workflow():
    incident_report = ServiceNow_incident__4_0_0__retrievewithwhere_incident()
    ticket_id = Zendesk_Service_Ticket__2_0_0__create_Ticket()
    Zendesk_Service_ticketAttachment__2_0_0__UPLOADATTACHMENT_ticketAttachment(ticket_id, incident_report)
