# uid 95

## Gold nodes

-   g1  block    contacts = Salesforce_Contact__5_0_0__retrievewithwhere_Contact(contacts_CleanStatus_0=contacts_CleanStatus_0, contacts_CleanStatus_1=contacts_CleanStatus_1)
-   g2  loop     for contact in contacts
-   g3  gateway  contact['CleanStatus'] == 'new'
-   g4  block    updated_contact = Salesforce_Contact__5_0_0__updatewithwhere_Contact()
-   g5  block    task = user_task('check compliance')
-   g6  return   return None

## Gold edges

- g3 --true--> g4
- g3 --false--> g5
- g2 --enter--> g3
- g4 --back--> g2
- g5 --back--> g2
- g1 --seq--> g2
- g2 --seq--> g6

## Extracted nodes

-     node_1  block    contacts = Salesforce_Contact__5_0_0__retrievewithwhere_Contact(contacts_CleanStatus_0=contacts_CleanStatus_0, contacts_CleanStatus_1=contacts_CleanStatus_1)
-     node_2  loop     iter contacts
-     node_3  block    
-     node_4  gateway  contact['CleanStatus'] == 'new'
-     node_5  block    updated_contact = Salesforce_Contact__5_0_0__updatewithwhere_Contact()
-     node_6  block    task = user_task('check compliance')
-     node_7  block    
-     node_8  return   return None

## Extracted edges

- node_4 --contact['CleanStatus'] == 'new'--> node_5
- node_4 --not (contact['CleanStatus'] == 'new')--> node_6
- node_5 ----> node_7
- node_6 ----> node_7
- node_2 --next(contacts)--> node_4
- node_2 --exhausted(contacts)--> node_3
- node_7 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_8
