# SpiffWorkflow Generated Implementation
import time

def select_product_and_quantity():
    """Task: Select_Product_and_Quantity"""
    print("Executing Select_Product_and_Quantity")
    return True

def select_product_color():
    """Task: Select_Product_Color"""
    print("Executing Select_Product_Color")
    return True

def select_product_size():
    """Task: Select_Product_Size"""
    print("Executing Select_Product_Size")
    return True

def select_product_style():
    """Task: Select_Product_Style"""
    print("Executing Select_Product_Style")
    return True

def continue_shopping():
    """Task: Continue_Shopping?"""
    print("Executing Continue_Shopping?")
    return True

def look_up_product_price():
    """Task: Look_Up_Product__Price"""
    print("Executing Look_Up_Product__Price")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    select_product_and_quantity()
    select_product_color()
    select_product_size()
    select_product_style()
    continue_shopping()
    look_up_product_price()
    return True

if __name__ == "__main__":
    run_workflow()
