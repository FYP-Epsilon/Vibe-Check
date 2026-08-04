# SpiffWorkflow Generated Implementation
import time

def add_xero_invoice():
    """Task: Add_Xero_Invoice"""
    print("Executing Add_Xero_Invoice")
    return True

def get_xero_currencies():
    """Task: Get_Xero_Currencies"""
    print("Executing Get_Xero_Currencies")
    return True

def build_enumeration():
    """Task: Build_Enumeration"""
    print("Executing Build_Enumeration")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    add_xero_invoice()
    get_xero_currencies()
    build_enumeration()
    return True

if __name__ == "__main__":
    run_workflow()
