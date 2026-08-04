# SpiffWorkflow Generated Implementation
import time

def show_times():
    """Task: Show_Times"""
    print("Executing Show_Times")
    return True

def choose_a_vaule():
    """Task: Choose_a_vaule"""
    print("Executing Choose_a_vaule")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    show_times()
    choose_a_vaule()
    return True

if __name__ == "__main__":
    run_workflow()
