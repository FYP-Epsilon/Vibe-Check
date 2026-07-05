def Coupa_invoices__4_0_0__retrievewithwhere_invoices():
    return {}

def Coupa_suppliers__4_0_0__create_suppliers():
    return {}

def Coupa_purchase_orders__4_0_0__retrievewithwhere_purchase_orders():
    return {}

def Coupa_users__4_0_0__retrievewithwhere_users():
    return {}

def workflow():
    purchase_orders = Coupa_purchase_orders__4_0_0__retrievewithwhere_purchase_orders()
    users = Coupa_users__4_0_0__retrievewithwhere_users()
    supplier = Coupa_suppliers__4_0_0__create_suppliers()
    return None
