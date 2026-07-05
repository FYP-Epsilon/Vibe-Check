# uid 14

## Gold nodes

-   g1  block    campaigns = Marketo_campaigns__3_0_0__retrievewithwhere_campaigns(campaigns_type_0=campaigns_type_0, campaigns_type_1=campaigns_type_1)
-   g2  loop     for campaign in campaigns
-   g3  gateway  campaign['type'] == 'Finance'
-   g4  block    applicants = Microsoft_Dynamics_365_for_Finance_and_Operations_Applicant__2_0_0__retrievewithwhere_Applicant()
-   g5  block    board = monday_com_Board__2_0_0__create_Board()
-   g6  return   return None

## Gold edges

- g4 --seq--> g5
- g3 --true--> g4
- g2 --enter--> g3
- g5 --back--> g2
- g3 --back--> g2
- g1 --seq--> g2
- g2 --seq--> g6

## Extracted nodes

-     node_1  block    campaigns = Marketo_campaigns__3_0_0__retrievewithwhere_campaigns(campaigns_type_0=campaigns_type_0, campaigns_type_1=campaigns_type_1)
-     node_2  loop     iter campaigns
-     node_3  block    
-     node_4  gateway  campaign['type'] == 'Finance'
-     node_5  block    applicants = Microsoft_Dynamics_365_for_Finance_and_Operations_Applicant__2_0_0__retrievewithwhere_Applicant()
-     node_6  block    board = monday_com_Board__2_0_0__create_Board()
-     node_7  block    
-     node_8  block    
-     node_9  return   return None

## Extracted edges

- node_5 ----> node_6
- node_4 --campaign['type'] == 'Finance'--> node_5
- node_4 --not (campaign['type'] == 'Finance')--> node_7
- node_6 ----> node_8
- node_7 ----> node_8
- node_2 --next(campaigns)--> node_4
- node_2 --exhausted(campaigns)--> node_3
- node_8 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_9
