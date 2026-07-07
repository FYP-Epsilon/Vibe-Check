def Amazon_SNS_Subscription__3_0_0__retrievewithwhere_Subscription():
    return {}


def Amazon_SNS_Subscription__3_0_0__create_Subscription():
    return {}


def workflow():
    Amazon_SNS_Subscription__3_0_0__create_Subscription(TopicArn='arn:aws:sns:us-west-2:123456789012:dogs', Protocol='email', Endpoint='your.email@example.com')
    subscriptions = Amazon_SNS_Subscription__3_0_0__retrievewithwhere_Subscription()
    for subscription in subscriptions:
        print(subscription)
