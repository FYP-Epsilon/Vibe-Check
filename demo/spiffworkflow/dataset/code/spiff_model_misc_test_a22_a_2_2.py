# SpiffWorkflow Generated Implementation
import time

def task_1():
    """Task: Task_1"""
    print("Executing Task_1")
    return True

def task_a():
    """Task: Task_A"""
    print("Executing Task_A")
    return True

def task_b():
    """Task: Task_B"""
    print("Executing Task_B")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    task_1()
    task_a()
    task_b()
    return True

if __name__ == "__main__":
    run_workflow()
