# SpiffWorkflow Generated Implementation
import time

def initiator_one():
    """Task: Initiator_One"""
    print("Executing Initiator_One")
    return True

def finance_approval():
    """Task: Finance_Approval"""
    print("Executing Finance_Approval")
    return True

def initiator_two():
    """Task: Initiator_Two"""
    print("Executing Initiator_Two")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    initiator_one()
    finance_approval()
    initiator_two()
    return True

if __name__ == "__main__":
    run_workflow()
