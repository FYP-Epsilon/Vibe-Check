# uid 32

## Gold nodes

-   g1  block    project = GitLab_Project__5_0_0__create_Project()
-   g2  block    message = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-   g3  block    task = user_task('check with manager')
-   g4  return   return None

## Gold edges

- g1 --seq--> g2
- g2 --seq--> g3
- g3 --seq--> g4

## Extracted nodes

-     node_1  block    project = GitLab_Project__5_0_0__create_Project()
-     node_2  block    message = Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages()
-     node_3  block    task = user_task('check with manager')
-     node_4  return   return None

## Extracted edges

- node_1 ----> node_2
- node_2 ----> node_3
- node_3 ----> node_4
