def Microsoft_Exchange_Events__2_0_0__create_Events():
    return {}


def Calendly_schedulingLink__1_0_0__create_schedulingLink():
    return {}


def workflow():
    event_id = Microsoft_Exchange_Events__2_0_0__create_Events()
    scheduling_link = Calendly_schedulingLink__1_0_0__create_schedulingLink()
    print(f'Shared calendar event link: {scheduling_link}')
