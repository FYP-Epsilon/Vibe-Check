def Salesforce_Contact__5_0_0__create_Contact():
    return {}


def Gmail_mail__2_0_0__create_mail():
    return {}


def Box_File__3_0_0__create_File():
    return {}


def Box_Folder__3_0_0__create_Folder():
    return {}


def workflow():
    contact = Salesforce_Contact__5_0_0__create_Contact()
    contact_id = contact['Id']
    folder = Box_Folder__3_0_0__create_Folder()
    file = Box_File__3_0_0__create_File(folder['id'], 'Contact ' + str(contact_id) + '.txt', contact)
    file_id = file['id']
    mail = Gmail_mail__2_0_0__create_mail()
    mail['subject'] = 'New Contact: ' + contact['Name']
    mail['body'] = 'Name: ' + contact['Name'] + '\nEmail: ' + contact['Email'] + '\nPhone: ' + contact['Phone']
    mail['attachments'] = [file_id]
    Gmail_mail__2_0_0__create_mail(mail)
