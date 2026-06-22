def process_loan_application(credit_score: int, requested_amount: float, active_bank_account: bool) -> str:
    # State variables
    status = "PENDING"
    approved_amount = 0.0

    # Business constraints
    if not active_bank_account:
        status = "REJECTED_NO_ACCOUNT"
        return status

    if credit_score < 600:
        status = "REJECTED_POOR_CREDIT"
    elif credit_score >= 600 and credit_score < 750:
        if requested_amount <= 5000.0:
            status = "APPROVED_TIER_2"
            approved_amount = requested_amount
        else:
            status = "REJECTED_AMOUNT_TOO_HIGH"
    else:
        # credit_score >= 750
        status = "APPROVED_TIER_1"
        approved_amount = requested_amount

    # Artificial silent step (to test Gotcha 1: Stutter Elimination)
    temp_audit_log = f"Processed {approved_amount} for score {credit_score}"
    
    return status
