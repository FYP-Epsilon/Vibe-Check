def Amazon_SNS_Subscription__3_0_0__retrievewithwhere_Subscription():
    return {}


def Amazon_SNS_Subscription__3_0_0__create_Subscription():
    return {}


def workflow():
    Amazon_SNS_Subscription__3_0_0__create_Subscription('dogs', 'http://example.com/dogs')
    subscriptions = Amazon_SNS_Subscription__3_0_0__retrievewithwhere_Subscription('all')
    for subscription in subscriptions:
        if subscription != 'dogs':
            print(subscription)
