def Amazon_S3_object__2_0_0__retrievewithwhere_object():
    return {}


def Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket():
    return {}


def workflow():
    buckets = Amazon_S3_bucket__2_0_0__retrievewithwhere_bucket()
    if buckets == Null:
        objects = Amazon_S3_object__2_0_0__retrievewithwhere_object()
    return None
