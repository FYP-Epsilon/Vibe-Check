def bambooHR_employees__2_0_0__retrievewithwhere_employees():
    return {}

def Zendesk_Service_Ticket__2_0_0__create_Ticket():
    return {}

def Microsoft_Teams_ChatMessage__2_0_0__create_ChatMessage():
    return {}

def bambooHR_dependents__2_0_0__retrievewithwhere_dependents():
    return {}

def workflow():
    dependents = bambooHR_dependents__2_0_0__retrievewithwhere_dependents()
    ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket()
    message = Microsoft_Teams_ChatMessage__2_0_0__create_ChatMessage()
    return None
