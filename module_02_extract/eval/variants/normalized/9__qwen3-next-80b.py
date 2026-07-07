def GitHub_Comment__3_0_0__retrievewithwhere_Comment(comments_author_0: str = None, comments_author_1: str = None):
    return [{"author": comments_author_0}, {"author": comments_author_1}]


def GitHub_Repository__3_0_0__retrievewithwhere_Repository():
    return [{'value': 0}, {'value': 1}]


def GitHub_Issue__3_0_0__retrievewithwhere_Issue():
    return [{'value': 0}, {'value': 1}]


def Slack_message__3_0_0__create_message():
    return {}


def workflow(comments_author_0: str, comments_author_1: str):
    repos = GitHub_Repository__3_0_0__retrievewithwhere_Repository()
    for repo in repos:
        issues = GitHub_Issue__3_0_0__retrievewithwhere_Issue()
        for issue in issues:
            comments = GitHub_Comment__3_0_0__retrievewithwhere_Comment(comments_author_0=comments_author_0, comments_author_1=comments_author_1)
            for comment in comments:
                if comment['get']('author') in [comments_author_0, comments_author_1]:
                    Slack_message__3_0_0__create_message()
