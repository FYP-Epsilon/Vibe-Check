# SpiffWorkflow Generated Implementation
import time

def set_variables():
    """Task: Set_Variables"""
    print("Executing Set_Variables")
    return True

def display_variables():
    """Task: Display_Variables"""
    print("Executing Display_Variables")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    set_variables()
    display_variables()
    return True

if __name__ == "__main__":
    run_workflow()
