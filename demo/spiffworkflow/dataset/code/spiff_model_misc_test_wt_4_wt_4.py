# SpiffWorkflow Generated Implementation
import time

def set_name():
    """Task: Set_Name"""
    print("Executing Set_Name")
    return True

def check_name():
    """Task: Check_Name"""
    print("Executing Check_Name")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    set_name()
    check_name()
    return True

if __name__ == "__main__":
    run_workflow()
