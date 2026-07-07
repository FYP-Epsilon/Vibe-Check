def Microsoft_Dynamics_365_for_Sales_Invoice__7_0_0__retrievewithwhere_Invoice():
    return {}


def Slack_message__3_0_0__create_message():
    return {}


def Microsoft_Dynamics_365_for_Sales_PriceLevel__7_0_0__retrievewithwhere_PriceLevel():
    return {}


def Microsoft_Dynamics_365_for_Sales_SalesOrder__7_0_0__retrievewithwhere_SalesOrder():
    return {}


def Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages():
    return {}


def workflow():
    invoices = Microsoft_Dynamics_365_for_Sales_Invoice__7_0_0__retrievewithwhere_Invoice()
    if invoices:
        Slack_message__3_0_0__create_message('New invoices received')
        price_levels = Microsoft_Dynamics_365_for_Sales_PriceLevel__7_0_0__retrievewithwhere_PriceLevel()
        sales_orders = Microsoft_Dynamics_365_for_Sales_SalesOrder__7_0_0__retrievewithwhere_SalesOrder()
        email_body = f'Invoices: {invoices}\nPrice Levels: {price_levels}\nSales Orders: {sales_orders}'
        Microsoft_Exchange_Messages__2_0_0__SENDOUTLOOK_Messages('Manager', email_body)
