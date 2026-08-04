# SpiffWorkflow Generated Implementation
import time

def continue_the_process():
    """Task: Continue_the_Process"""
    print("Executing Continue_the_Process")
    return True

def send_message():
    """Task: Send_Message"""
    print("Executing Send_Message")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    continue_the_process()
    send_message()
    return True

if __name__ == "__main__":
    run_workflow()
