# SpiffWorkflow Generated Implementation
import time

def get_filename():
    """Task: Get_Filename"""
    print("Executing Get_Filename")
    return True

def read_file():
    """Task: Read_File"""
    print("Executing Read_File")
    return True

def display_file_contents():
    """Task: Display_File_Contents"""
    print("Executing Display_File_Contents")
    return True

def show_filename():
    """Task: Show_Filename"""
    print("Executing Show_Filename")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    get_filename()
    read_file()
    display_file_contents()
    show_filename()
    return True

if __name__ == "__main__":
    run_workflow()
