"""Disputed (Q2): does «__init__.py експортує respond і всі типи types.py» include the alias `ItemType`?

Reading taken: yes — `ItemType` is a type of types.py, so `thinkhow.facilitation` exports it.
Not sealed until the slice planner answers Q2.
"""

import thinkhow.facilitation as facilitation
import thinkhow.facilitation.types as types


def test_package_exports_item_type_too() -> None:
    assert "ItemType" in facilitation.__all__
    assert facilitation.ItemType is types.ItemType
