# SpiffWorkflow Generated Implementation
import time

def my_script():
    """Task: My_Script"""
    print("Executing My_Script")
    return True

def is_wonderful():
    """Task: is_wonderful?"""
    print("Executing is_wonderful?")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    my_script()
    is_wonderful()
    return True

if __name__ == "__main__":
    run_workflow()
