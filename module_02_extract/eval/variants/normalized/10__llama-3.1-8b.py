def Amazon_S3_object__2_0_0__deletewithwhere_object(object_size: int = None):
    return {"size": object_size}


def Box_File__3_0_0__retrievewithwhere_File():
    return [{'value': 0}, {'value': 1}]


def Amazon_S3_bucket__2_0_0__create_bucket():
    return {}


def Amazon_S3_object__2_0_0__create_object():
    return {}


def workflow(object_size: int):
    bucket = Amazon_S3_bucket__2_0_0__create_bucket()
    for file in Box_File__3_0_0__retrievewithwhere_File():
        Amazon_S3_object__2_0_0__create_object(file, bucket)
        created_object = Amazon_S3_object__2_0_0__create_object(file, bucket)
        if created_object['size'] > object_size:
            Amazon_S3_object__2_0_0__deletewithwhere_object(created_object['size'])
