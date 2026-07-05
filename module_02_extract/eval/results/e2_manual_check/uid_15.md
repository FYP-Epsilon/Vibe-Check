# uid 15

## Gold nodes

-   g1  block    teams = Trello_Organization__2_0_0__retrievewithwhere_Organization(teams_name_0=teams_name_0, teams_name_1=teams_name_1)
-   g2  loop     for team in teams
-   g3  gateway  team['name'] == 'customer'
-   g4  block    lead = Marketo_leads__3_0_0__create_leads()
-   g5  gateway  team['name'] == 'internal'
-   g6  block    email = Gmail_mail__2_0_0__create_mail()
-   g7  return   return None

## Gold edges

- g3 --true--> g4
- g5 --true--> g6
- g3 --false--> g5
- g2 --enter--> g3
- g4 --back--> g2
- g6 --back--> g2
- g5 --back--> g2
- g1 --seq--> g2
- g2 --seq--> g7

## Extracted nodes

-     node_1  block    teams = Trello_Organization__2_0_0__retrievewithwhere_Organization(teams_name_0=teams_name_0, teams_name_1=teams_name_1)
-     node_2  loop     iter teams
-     node_3  block    
-     node_4  gateway  team['name'] == 'customer'
-     node_5  block    lead = Marketo_leads__3_0_0__create_leads()
-     node_6  gateway  team['name'] == 'internal'
-     node_7  block    email = Gmail_mail__2_0_0__create_mail()
-     node_8  block    
-     node_9  block    
-    node_10  block    
-    node_11  return   return None

## Extracted edges

- node_6 --team['name'] == 'internal'--> node_7
- node_6 --not (team['name'] == 'internal')--> node_8
- node_7 ----> node_9
- node_8 ----> node_9
- node_4 --team['name'] == 'customer'--> node_5
- node_4 --not (team['name'] == 'customer')--> node_6
- node_5 ----> node_10
- node_9 ----> node_10
- node_2 --next(teams)--> node_4
- node_2 --exhausted(teams)--> node_3
- node_10 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_11
