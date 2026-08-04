# SpiffWorkflow Generated Implementation
import time

def select_product_and_quantity():
    """Task: Select_Product_and_Quantity"""
    print("Executing Select_Product_and_Quantity")
    return True

def calculate_order_total():
    """Task: Calculate_Order_Total"""
    print("Executing Calculate_Order_Total")
    return True

def review_order():
    """Task: Review_Order"""
    print("Executing Review_Order")
    return True

def look_up_product_price():
    """Task: Look_Up_Product__Price"""
    print("Executing Look_Up_Product__Price")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    select_product_and_quantity()
    calculate_order_total()
    review_order()
    look_up_product_price()
    return True

if __name__ == "__main__":
    run_workflow()
