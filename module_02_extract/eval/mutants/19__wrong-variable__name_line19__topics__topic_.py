def Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_topicarn_0: str=None, topics_topicarn_1: str=None):
    return [{'topicarn': topics_topicarn_0}, {'topicarn': topics_topicarn_1}]

def ServiceNow_incident__4_0_0__create_incident():
    return {}

def Zendesk_Service_Ticket__2_0_0__create_Ticket():
    return {}

def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}

def workflow(topics_topicarn_0: str, topics_topicarn_1: str):
    topics = Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_topicarn_0=topics_topicarn_0, topics_topicarn_1=topics_topicarn_1)
    for topic in topic:
        if topic['topicarn'] == 'critical':
            email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
            ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket()
            incident = ServiceNow_incident__4_0_0__create_incident()
    return None
