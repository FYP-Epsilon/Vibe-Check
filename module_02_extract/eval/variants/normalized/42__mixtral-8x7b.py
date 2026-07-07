def Microsoft_Exchange_Events__2_0_0__create_Events():
    return {}


def Calendly_schedulingLink__1_0_0__create_schedulingLink():
    return {}


def workflow():
    event = Microsoft_Exchange_Events__2_0_0__create_Events(subject='New Event', start='2023-03-01T09:00:00', end='2023-03-01T10:00:00')
    event_id = event['Id']
    scheduling_link = Calendly_schedulingLink__1_0_0__create_schedulingLink(event_ids=[event_id], event_type='one-on-one', duration='01:00')
    return scheduling_link['url']
