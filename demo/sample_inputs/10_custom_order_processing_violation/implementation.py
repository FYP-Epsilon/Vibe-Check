def Receive_Customer_Order(order_id: str = "ORD-9912"):
    return {"order_id": order_id, "amount": 250.0}


def Check_Inventory_Stock(order: dict):
    return {"in_stock": True}


def Assess_Risk_Score(order: dict):
    return {"risk_score": 85}


def Process_Credit_Payment(order: dict):
    return {"payment_status": "processed"}


def Send_Fraud_Alert_Email(order: dict):
    return {"email_sent": True}


def Fulfill_Standard_Shipping(order: dict):
    return {"tracking_num": "TRK-5541"}


def workflow(order_id: str = "ORD-9912"):
    order = Receive_Customer_Order(order_id)
    inventory = Check_Inventory_Stock(order)
    risk = Assess_Risk_Score(order)

    if risk.get("risk_score", 0) > 80:
        # VIOLATION: Fraud Alert Email sent BEFORE Credit Payment processing!
        alert = Send_Fraud_Alert_Email(order)
        payment = Process_Credit_Payment(order)
    else:
        shipping = Fulfill_Standard_Shipping(order)
