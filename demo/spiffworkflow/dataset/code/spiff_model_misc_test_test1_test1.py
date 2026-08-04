# SpiffWorkflow Generated Implementation
import time

def set_test():
    """Task: Set_Test"""
    print("Executing Set_Test")
    return True

def test():
    """Task: Test"""
    print("Executing Test")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    set_test()
    test()
    return True

if __name__ == "__main__":
    run_workflow()
