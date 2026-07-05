def Amazon_S3_object__2_0_0__deletewithwhere_object(object_size: int=None):
    return {'size': object_size}

def Box_File__3_0_0__retrievewithwhere_File():
    return [{'value': 0}, {'value': 1}]

def Amazon_S3_bucket__2_0_0__create_bucket():
    return {}

def Amazon_S3_object__2_0_0__create_object():
    return {}

def workflow(object_size: int):
    files = Box_File__3_0_0__retrievewithwhere_File()
    for file in files:
        object = Amazon_S3_object__2_0_0__create_object()
        if object['size'] > 100:
            object = Amazon_S3_object__2_0_0__deletewithwhere_object(object_size=object_size)
    return None
