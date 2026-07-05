# uid 4

## Gold nodes

-   g1  block    issues = Jira_Issue__2_0_0__retrievewithwhere_Issue(issues_priority_0=issues_priority_0, issues_priority_1=issues_priority_1)
-   g2  loop     for issue in issues
-   g3  gateway  issue['priority'] == 'urgent'
-   g4  block    task = Asana_Tasks__2_0_0__create_Tasks()
-   g5  block    email = Gmail_mail__2_0_0__create_mail()
-   g6  gateway  issue['priority'] == 'low'
-   g7  block    message = Slack_message__3_0_0__create_message()
-   g8  return   return None

## Gold edges

- g4 --seq--> g5
- g3 --true--> g4
- g6 --true--> g7
- g3 --false--> g6
- g2 --enter--> g3
- g5 --back--> g2
- g7 --back--> g2
- g6 --back--> g2
- g1 --seq--> g2
- g2 --seq--> g8

## Extracted nodes

-     node_1  block    issues = Jira_Issue__2_0_0__retrievewithwhere_Issue(issues_priority_0=issues_priority_0, issues_priority_1=issues_priority_1)
-     node_2  loop     iter issues
-     node_3  block    
-     node_4  gateway  issue['priority'] == 'urgent'
-     node_5  block    task = Asana_Tasks__2_0_0__create_Tasks()
-     node_6  block    email = Gmail_mail__2_0_0__create_mail()
-     node_7  gateway  issue['priority'] == 'low'
-     node_8  block    message = Slack_message__3_0_0__create_message()
-     node_9  block    
-    node_10  block    
-    node_11  block    
-    node_12  return   return None

## Extracted edges

- node_5 ----> node_6
- node_7 --issue['priority'] == 'low'--> node_8
- node_7 --not (issue['priority'] == 'low')--> node_9
- node_8 ----> node_10
- node_9 ----> node_10
- node_4 --issue['priority'] == 'urgent'--> node_5
- node_4 --not (issue['priority'] == 'urgent')--> node_7
- node_6 ----> node_11
- node_10 ----> node_11
- node_2 --next(issues)--> node_4
- node_2 --exhausted(issues)--> node_3
- node_11 ----> node_2
- node_1 ----> node_2
- node_3 ----> node_12
