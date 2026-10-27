"""The owner's page of learning (learning-loop S3): the feed of changes, what the version check refused,
the observations — in Ukrainian, as the Knowledge itself (M3 A5). Reads only; the rollback is
`knowledge.rollback`.
"""

from dataclasses import dataclass

from thinkhow import knowledge
from thinkhow.learning.observations import Observation, read_all
from thinkhow.learning.synthesize import SynthesisRun, runs
from thinkhow.platform.storage import Storage


@dataclass(frozen=True)
class LearningView:
    feed: list[knowledge.ChangeView]
    rejected: list[SynthesisRun]
    observations: list[Observation]
    links: dict[str, str]


def learning_view(storage: Storage) -> LearningView:
    """Flow: the changes newest first, the refused runs newest first, the observations newest first."""
    observations = read_all(storage)
    refused = [run for run in runs(storage) if run.outcome == "rejected"]
    return LearningView(
        feed=knowledge.changes(storage),
        rejected=sorted(refused, key=lambda run: run.at, reverse=True),
        observations=sorted(observations, key=lambda o: o.analyzed_at, reverse=True),
        links={o.id: o.link for o in observations},
    )
