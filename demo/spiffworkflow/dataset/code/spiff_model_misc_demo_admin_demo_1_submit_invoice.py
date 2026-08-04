# SpiffWorkflow Generated Implementation
import time

def submit_invoice():
    """Task: Submit_Invoice"""
    print("Executing Submit_Invoice")
    return True

def save_invoice_date_to_dyamodb():
    """Task: Save_Invoice_Date_to_DyamoDB"""
    print("Executing Save_Invoice_Date_to_DyamoDB")
    return True

def save_pdf_document_to_s3():
    """Task: Save_PDF_Document_to_S3"""
    print("Executing Save_PDF_Document_to_S3")
    return True

def send_waku_message_invoice_submitted():
    """Task: Send_Waku_Message:_Invoice_Submitted"""
    print("Executing Send_Waku_Message:_Invoice_Submitted")
    return True

def get_bamboo_salary():
    """Task: Get_Bamboo_Salary"""
    print("Executing Get_Bamboo_Salary")
    return True

def create_invoice_in_xero():
    """Task: Create_Invoice_in_Xero"""
    print("Executing Create_Invoice_in_Xero")
    return True

def send_waku_message_invoice_rejected():
    """Task: Send_Waku_Message:_Invoice_Rejected"""
    print("Executing Send_Waku_Message:_Invoice_Rejected")
    return True

def send_waku_message_invoice_approved():
    """Task: Send_Waku_Message:_Invoice_Approved"""
    print("Executing Send_Waku_Message:_Invoice_Approved")
    return True

def convert_bamboo_annual_salary():
    """Task: Convert_Bamboo_Annual_Salary"""
    print("Executing Convert_Bamboo_Annual_Salary")
    return True

def check_match():
    """Task: Check_Match?"""
    print("Executing Check_Match?")
    return True

def run_workflow():
    """Driver function executing tasks in BPMN sequence."""
    submit_invoice()
    save_invoice_date_to_dyamodb()
    save_pdf_document_to_s3()
    send_waku_message_invoice_submitted()
    get_bamboo_salary()
    create_invoice_in_xero()
    send_waku_message_invoice_rejected()
    send_waku_message_invoice_approved()
    convert_bamboo_annual_salary()
    check_match()
    return True

if __name__ == "__main__":
    run_workflow()
