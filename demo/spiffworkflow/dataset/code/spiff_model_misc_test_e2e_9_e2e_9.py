# SpiffWorkflow Generated Implementation
import time

def enter_value():
    """Task: Enter_value"""
    print("Executing Enter_value")
    return True

def display_value():
    """Task: Display_value"""
    print("Executing Display_value")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    enter_value()
    display_value()
    return True

if __name__ == "__main__":
    run_workflow()
