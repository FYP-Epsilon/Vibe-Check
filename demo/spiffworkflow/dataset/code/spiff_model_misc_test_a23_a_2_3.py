# SpiffWorkflow Generated Implementation
import time

def task_a():
    """Task: Task_A"""
    print("Executing Task_A")
    return True

def task_b():
    """Task: Task_B"""
    print("Executing Task_B")
    return True

def test():
    """Task: test"""
    print("Executing test")
    return True

def additional():
    """Task: additional"""
    print("Executing additional")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    task_a()
    task_b()
    test()
    additional()
    return True

if __name__ == "__main__":
    run_workflow()
