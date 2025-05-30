## 302 See Other

I should make some system for automatic syncing between this document and https://github.com/python-caldav/caldav/issues/474 - currently the latter has been updated while this one hasn't.

### GitHub Issues vs Git

The GitHub issues features easy possibilities for feedback and comments for any GitHub user and it features better linking (with embedded information on what issues and pull requests are merged/fixed/closed).  It also does have the history available.

Having the roadmap in the repository itself provides platform-independence (there is much talk in Europe nowadays that it's needed to have a "Plan B" or an "Exit plan" and not depend too much on cloud services in the USA), it also preserves the history of the document in a standard way with zero trust needed.

I would like to have both, and it should be easily programmable, but I have other priorities so I'm not fixing it now, and manually syncing it is too much of a pain (and will inevitably cause inconsistencies).

Update: I asked a popular AI search robot about how to do a one-way sync, and it came up with the following answer:

```
import requests

ISSUE_COMMENTS_URL = "https://api.github.com/repos/python-caldav/caldav/issues/474/comments"
COMMENT_ID = 3040767277
OUTPUT_FILE = "ROADMAP.md"

def fetch_comment():
    response = requests.get(ISSUE_COMMENTS_URL)
    response.raise_for_status()
    comments = response.json()
    for comment in comments:
        if comment["id"] == COMMENT_ID:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(comment["body"])
            print(f"Comment saved to {OUTPUT_FILE}")
            return
    print("Comment not found.")

if __name__ == "__main__":
    fetch_comment()
```
