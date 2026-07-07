def Marketo_leads__3_0_0__create_leads():
    return {}


def Slack_message__3_0_0__create_message():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    leads = Marketo_leads__3_0_0__create_leads(first_name='John', last_name='Doe', email='john.doe@example.com')
    leads += Marketo_leads__3_0_0__create_leads(first_name='Jane', last_name='Doe', email='jane.doe@example.com')
    Slack_message__3_0_0__create_message(text='Two new leads have been created:\n1. John Doe (john.doe@example.com)\n2. Jane Doe (jane.doe@example.com)', channel='#stakeholders', label='New Leads')
    user_task(label='Follow up with stakeholders about new leads')
