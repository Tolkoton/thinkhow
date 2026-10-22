"""Disputed (Q1): the owner (who passes the read rule for any uid) opens a ref whose uid is not by the regex.

Reading taken: «ідентифікатор не за виразом» covers the uid of a TopicRef too, so the answer is TopicNotFound
(not the storage's ValueError for an unsafe path). Not sealed until the slice planner answers Q1.
"""

from pathlib import Path

import pytest
from skelw_fakes import ALICE, OWNER, T0

from thinkhow.platform.storage import LocalStorage
from thinkhow.workspace import TopicNotFound, TopicRef, create_topic, open_topic


def test_owner_open_with_malformed_uid_is_topic_not_found(tmp_path: Path) -> None:
    store = LocalStorage(tmp_path)
    tid = create_topic(store, ALICE, "Тема", T0)
    for uid in ["..", "", "alice-1/..", "bad.uid", "a" * 129]:
        with pytest.raises(TopicNotFound):
            open_topic(store, OWNER, TopicRef(uid, tid), T0)
