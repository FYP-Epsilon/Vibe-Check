# SpiffWorkflow Generated Implementation
import time

def complete_form():
    """Task: Complete_Form"""
    print("Executing Complete_Form")
    return True

def based_on_last_name_set_awesomeness():
    """Task: Based_on_last_name,_set_awesomeness"""
    print("Executing Based_on_last_name,_set_awesomeness")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    complete_form()
    based_on_last_name_set_awesomeness()
    return True

if __name__ == "__main__":
    run_workflow()
