"""A sealed title is cacheable: SQLAlchemy reads `cache_ok` from the subclass itself, so `SealedTitle`
without its own flag made every query on reminders and documents skip the statement cache and warn."""

from __future__ import annotations

import warnings

from sqlalchemy import Column, Integer, MetaData, Table, select

from tessellate.core.database import SealedText, SealedTitle


def test_each_sealed_type_declares_its_own_cache_ok():
    for kind in (SealedText, SealedTitle):
        assert kind.__dict__.get("cache_ok") is True, kind.__name__


def test_a_query_on_a_sealed_title_makes_a_cache_key_without_a_warning():
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("title", SealedTitle(200)))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        key = select(table.c.title).where(table.c.title == "x")._generate_cache_key()
    assert key is not None
