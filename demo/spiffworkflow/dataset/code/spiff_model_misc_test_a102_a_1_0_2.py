# SpiffWorkflow Generated Implementation
import time

def task_1():
    """Task: Task_1"""
    print("Executing Task_1")
    return True

def task_2():
    """Task: Task_2"""
    print("Executing Task_2")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    task_1()
    task_2()
    return True

if __name__ == "__main__":
    run_workflow()
