def AWS_Lambda_function__2_0_0__INVOKEFUNCTION_function():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    user_task('Starting calculator...')
    num1 = user_task('Enter the first number:')
    operator = user_task('Enter an operator (+, -, *, /):')
    num2 = user_task('Enter the second number:')
    if operator == '+':
        result = num1 + num2
    elif operator == '-':
        result = num1 - num2
    elif operator == '*':
        result = num1 * num2
    elif operator == '/':
        if num2 != 0:
            result = num1 / num2
        else:
            user_task('Error: Division by zero is not allowed.')
            return
    else:
        user_task('Invalid operator. Please use +, -, *, or /.')
        return
    user_task(f'Result: {result}')
    AWS_Lambda_function__2_0_0__INVOKEFUNCTION_function('calculator_complete', {'result': result})
