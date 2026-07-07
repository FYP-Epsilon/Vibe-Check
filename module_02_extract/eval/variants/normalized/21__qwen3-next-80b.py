def Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_type_0: str = None, topics_type_1: str = None):
    return [{"type": topics_type_0}, {"type": topics_type_1}]


def Zendesk_Service_Ticket__2_0_0__create_Ticket():
    return {}


def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def workflow(topics_type_0: str, topics_type_1: str):
    topics = Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_type_0, topics_type_1)
    for topic in topics:
        if topic['get']('type') == 'critical':
            Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
            Zendesk_Service_Ticket__2_0_0__create_Ticket()
