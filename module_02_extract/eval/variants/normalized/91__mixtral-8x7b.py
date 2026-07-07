def Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket():
    return [{'value': 0}, {'value': 1}]


def Amazon_SNS_Topic__3_0_0__PUBLISHMESSAGEONTOPIC_Topic():
    return {}


def workflow():
    bucket = Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket()
    steps = bucket['Steps']
    for step in steps:
        if step != 'send notification':
            steps['remove'](step)
    for step in steps:
        if step == 'send notification':
            Amazon_SNS_Topic__3_0_0__PUBLISHMESSAGEONTOPIC_Topic(step)
