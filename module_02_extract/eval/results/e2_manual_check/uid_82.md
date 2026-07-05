# uid 82

## Gold nodes

-   g1  block    board = Trello_Board__2_0_0__create_Board()
-   g2  block    board = Trello_Board__2_0_0__updatewithwhere_Board()
-   g3  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-   g4  block    card = Trello_Card__2_0_0__create_Card()
-   g5  block    card = Trello_Member__2_0_0__create_Member()
-   g6  return   return None

## Gold edges

- g1 --seq--> g2
- g2 --seq--> g3
- g3 --seq--> g4
- g4 --seq--> g5
- g5 --seq--> g6

## Extracted nodes

-     node_1  block    board = Trello_Board__2_0_0__create_Board()
-     node_2  block    board = Trello_Board__2_0_0__updatewithwhere_Board()
-     node_3  block    email = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-     node_4  block    card = Trello_Card__2_0_0__create_Card()
-     node_5  block    card = Trello_Member__2_0_0__create_Member()
-     node_6  return   return None

## Extracted edges

- node_1 ----> node_2
- node_2 ----> node_3
- node_3 ----> node_4
- node_4 ----> node_5
- node_5 ----> node_6
