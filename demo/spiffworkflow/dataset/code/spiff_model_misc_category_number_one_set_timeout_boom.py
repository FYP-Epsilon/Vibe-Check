# SpiffWorkflow Generated Implementation
import time

def show_timeout_value():
    """Task: show_timeout_value"""
    print("Executing show_timeout_value")
    return True

def set_timeout_with_dmn_baby():
    """Task: set_timeout_with_DMN,_baby"""
    print("Executing set_timeout_with_DMN,_baby")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    show_timeout_value()
    set_timeout_with_dmn_baby()
    return True

if __name__ == "__main__":
    run_workflow()
