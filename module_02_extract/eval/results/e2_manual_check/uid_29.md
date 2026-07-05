# uid 29

## Gold nodes

-   g1  block    contact = Salesforce_Contact__5_0_0__create_Contact()
-   g2  block    folder = Box_Folder__3_0_0__create_Folder()
-   g3  block    file = Box_File__3_0_0__create_File()
-   g4  block    mail = Gmail_mail__2_0_0__create_mail()
-   g5  return   return None

## Gold edges

- g1 --seq--> g2
- g2 --seq--> g3
- g3 --seq--> g4
- g4 --seq--> g5

## Extracted nodes

-     node_1  block    contact = Salesforce_Contact__5_0_0__create_Contact()
-     node_2  block    folder = Box_Folder__3_0_0__create_Folder()
-     node_3  block    file = Box_File__3_0_0__create_File()
-     node_4  block    mail = Gmail_mail__2_0_0__create_mail()
-     node_5  return   return None

## Extracted edges

- node_1 ----> node_2
- node_2 ----> node_3
- node_3 ----> node_4
- node_4 ----> node_5
