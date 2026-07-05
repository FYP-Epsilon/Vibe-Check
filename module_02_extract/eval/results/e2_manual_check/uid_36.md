# uid 36

## Gold nodes

-   g1  block    invoice = Coupa_invoices__4_0_0__create_invoices()
-   g2  block    expense_report = Coupa_expense_reports__4_0_0__create_expense_reports()
-   g3  return   return None

## Gold edges

- g1 --seq--> g2
- g2 --seq--> g3

## Extracted nodes

-     node_1  block    invoice = Coupa_invoices__4_0_0__create_invoices()
-     node_2  block    expense_report = Coupa_expense_reports__4_0_0__create_expense_reports()
-     node_3  return   return None

## Extracted edges

- node_1 ----> node_2
- node_2 ----> node_3
