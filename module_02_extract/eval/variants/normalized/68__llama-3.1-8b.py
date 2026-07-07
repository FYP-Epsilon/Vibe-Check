def Dropbox_files__3_0_0__retrievewithwhere_files():
    return {}


def user_task(label=None):
    return {'label': label}


def workflow():
    candidate_name = user_task(label='Enter candidate name')
    resume = Dropbox_files__3_0_0__retrievewithwhere_files()
    return (candidate_name, resume)
