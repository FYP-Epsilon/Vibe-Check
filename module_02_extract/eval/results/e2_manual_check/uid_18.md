# uid 18

## Gold nodes

-   g1  block    topics = Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_topicarn_0=topics_topicarn_0, topics_topicarn_1=topics_topicarn_1)
-   g2  loop     for topic in topics
-   g3  gateway  topic['topicarn'] == 'critical'
-   g4  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-   g5  block    ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket()
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

-     node_1  block    topics = Amazon_SNS_Topic__3_0_0__retrievewithwhere_Topic(topics_topicarn_0=topics_topicarn_0, topics_topicarn_1=topics_topicarn_1)
-     node_2  loop     iter topics
-     node_3  block    
-     node_4  gateway  topic['topicarn'] == 'critical'
-     node_5  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-     node_6  block    ticket = Zendesk_Service_Ticket__2_0_0__create_Ticket()
-     node_7  block    
-     node_8  block    
-     node_9  return   return None

## Extracted edges

- node_5 ----> node_6
- node_4 --topic['topicarn'] == 'critical'--> node_5
- node_4 --not (topic['topicarn'] == 'critical')--> node_7
- node_6 ----> node_8
- node_7 ----> node_8
- node_2 --next(topics)--> node_4
- node_2 --exhausted(topics)--> node_3
- node_8 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_9
