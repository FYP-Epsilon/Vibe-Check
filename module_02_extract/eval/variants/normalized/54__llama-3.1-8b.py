def bambooHR_timetracking__2_0_0__retrievewithwhere_timetracking():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    timesheet_data = bambooHR_timetracking__2_0_0__retrievewithwhere_timetracking()
    user_task('Reviewing employee timesheet')
    if not timesheet_data:
        user_task('Timesheet is empty or incomplete')
    else:
        user_task('Timesheet is complete and compliant')
