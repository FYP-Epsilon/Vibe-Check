def Amazon_S3_object__2_0_0__create_object():
    return {}


def Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket():
    return {}


def workflow():
    Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket('my_bucket')
    Amazon_S3_object__2_0_0__create_object('my_bucket', 'my_key', {'metadata': 'new object'})
