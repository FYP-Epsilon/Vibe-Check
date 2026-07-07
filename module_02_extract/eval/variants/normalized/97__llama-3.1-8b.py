def GitHub_Repository__3_0_0__retrievewithwhere_Repository():
    return [{'value': 0}, {'value': 1}]


def GitHub_Issue__3_0_0__create_Issue():
    return {}


def workflow():
    repository = GitHub_Repository__3_0_0__retrievewithwhere_Repository()
    for repo in repository:
        title = f"New issue in {repo['name']}"
        body = 'This is a new issue'
        GitHub_Issue__3_0_0__create_Issue(repo, title, body)
