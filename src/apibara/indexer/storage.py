from contextlib import contextmanager
from typing import (Any, Generic, Iterable, Iterator, List, NewType, Optional,
                    TypeVar)

from pymongo import MongoClient
from pymongo.client_session import ClientSession
from pymongo.database import Database

import apibara.cursor as cursor_utils
from apibara.protocol.proto.stream_pb2 import Cursor

Document = dict[str, Any]
DocumentFilter = dict[str, Any]
Update = dict[str, Any]
Projection = dict[str, any]

Filter = TypeVar("Filter")


class IndexerStorage(Generic[Filter]):
    """
    Manage indexers storage.
    """

    def __init__(self, url: Optional[str], indexer_id: str) -> None:
        if url is None:
            raise ValueError("Storage url must be not None")

        self.db_name = indexer_id.replace("-", "_")
        self._indexer_id = indexer_id

        self._mongo = MongoClient(url)
        self.db = self._mongo[self.db_name]

    @contextmanager
    def create_storage_for_block(self, cursor: Cursor) -> Iterator["Storage"]:
        with self._mongo.start_session() as session:
            yield Storage(self.db, session=session, cursor=cursor)

    @contextmanager
    def create_storage_for_data(self, cursor: Cursor) -> Iterator["Storage"]:
        with self._mongo.start_session() as session:
            yield Storage(self.db, session=session, cursor=cursor)
            self._update_cursor(cursor, session)

    @contextmanager
    def create_storage_for_invalidate(self, cursor: Cursor) -> Iterator["Storage"]:
        with self._mongo.start_session() as session:
            yield Storage(self.db, session=session, cursor=cursor)
            self._update_cursor(cursor, session)

    @contextmanager
    def create_storage_for_pending(self, cursor: Cursor) -> Iterator["Storage"]:
        with self._mongo.start_session() as session:
            yield Storage(self.db, session=session, cursor=cursor)

    def initialize(self, starting_cursor: Cursor, filter: Filter):
        existing = self.db["_apibara"].find_one({"indexer_id": self._indexer_id})
        if existing is not None:
            return
        self.db["_apibara"].insert_one(
            {
                "indexer_id": self._indexer_id,
                "cursor": cursor_utils.to_json(starting_cursor),
                "filter": filter,
            }
        )

    def starting_cursor(self) -> Optional[Cursor]:
        """Returns the starting cursor for the indexer."""
        state = self.db["_apibara"].find_one({"indexer_id": self._indexer_id})
        if state is None:
            return None
        return state.get("cursor")

    def filter(self) -> Optional[Filter]:
        """Returns the indexer filter."""
        state = self.db["_apibara"].find_one({"indexer_id": self._indexer_id})
        if state is None:
            return None

        cursor = state.get("cursor")
        if cursor is None:
            return None

        return Filter.from_json(cursor)

    def _update_filter(self, filter: Filter, session: ClientSession):
        """Set the indexer filter, overriding the previous filter."""
        self.db["_apibara"].update_one(
            {"indexer_id": self._indexer_id},
            {"$set": {"filter": filter.to_json()}},
            session=session,
        )

    def invalidate(self, cursor: Cursor):
        """Invalidates all data generate after `cursor`."""
        with self._mongo.start_session() as session:
            for collection in self.db.list_collections(session=session):
                name = collection["name"]
                if name.startswith("_"):
                    continue
                # remove items inserted after block_number
                self.db[name].delete_many(
                    {"_chain.valid_from": {"$gt": cursor.order_key}}, session=session
                )
                # rollback items updated after block_number
                self.db[name].update_many(
                    {"_chain.valid_to": {"$gt": cursor.order_key}},
                    {"$set": {"_chain.valid_to": None}},
                    session=session,
                )

    def drop_database(self):
        self._mongo.drop_database(self.db_name)

    def _update_cursor(self, cursor: Cursor, session: Optional[ClientSession] = None):
        self.db["_apibara"].update_one(
            {"indexer_id": self._indexer_id},
            {"$set": {"cursor": cursor.order_key}},
            upsert=True,
            session=session,
        )


class ReadOnlyStorage:
    """Chain-aware document storage, read methods."""

    def __init__(
        self, db: Database, *, session: Optional[ClientSession] = None
    ) -> None:
        self._db = db
        self._session = session

    async def find_one(
        self, collection: str, filter: DocumentFilter
    ) -> Optional[Document]:
        """Find the first document in `collection` matching `filter`."""
        self._add_current_block_to_filter(filter)
        return self._db[collection].find_one(filter, session=self._session)

    async def find(
        self,
        collection: str,
        filter: DocumentFilter,
        sort: Optional[dict[str, int]] = None,
        projection: Optional[Projection] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> Iterable[dict]:
        """Find all documents in `collection` matching `filter`.

        Arguments
        ---------
        - `collection`: the collection,
        - `filter`: the filter,
        - `sort`: keys used for sorting, e.g. `{"a": -1}` sorts documents by key `a` in descending order,
        - `project`: filter document keys to reduce the document size,
        - `skip`: number of documents to skip,
        - `limit`: maximum number of documents returned.
        """
        self._add_current_block_to_filter(filter)
        cursor = self._db[collection].find(
            filter, projection, skip, limit, session=self._session
        )
        if sort is not None:
            for field, order in sort.items():
                cursor = cursor.sort(field, order)
        return cursor

    def _add_current_block_to_filter(self, filter: DocumentFilter):
        filter["_chain.valid_to"] = None


class Storage(ReadOnlyStorage):
    """Chain-aware document storage."""

    def __init__(
        self, db: Database, cursor: Cursor, *, session: Optional[ClientSession] = None
    ) -> None:
        super().__init__(db, session=session)
        self._cursor = cursor

    async def insert_one(self, collection: str, doc: Document):
        """Insert `doc` into `collection`."""
        self._add_chain_information(doc)
        self._db[collection].insert_one(doc, session=self._session)

    async def insert_many(self, collection: str, docs: Iterable[Document]):
        """Insert multiple `docs` into `collection`."""
        for doc in docs:
            self._add_chain_information(doc)
        self._db[collection].insert_many(docs, session=self._session)

    async def delete_one(self, collection: str, filter: DocumentFilter):
        """ "Delete the first document in `collection` matching `filter`."""
        self._add_current_block_to_filter(filter)
        self._db[collection].update_one(
            filter,
            {"$set": {"_chain.valid_to": self._cursor.order_key}},
            session=self._session,
        )

    async def delete_many(self, collection: str, filter: DocumentFilter):
        """Delete all documents in `collection` matching `filter`."""
        self._add_current_block_to_filter(filter)
        self._db[collection].update_many(
            filter,
            {"$set": {"_chain.valid_to": self._cursor.order_key}},
            session=self._session,
        )

    async def find_one_and_replace(
        self,
        collection: str,
        filter: DocumentFilter,
        replacement: Document,
        upsert: bool = False,
    ):
        """Replace the first document in `collection` matching `filter` with `replacement`.
        If `upsert = True`, insert `replacement` even if no document matched the `filter`.
        """
        # Step 1. Update the old document (if any) by clamping its validity range
        self._add_current_block_to_filter(filter)
        existing = self._db[collection].find_one_and_update(
            filter,
            {"$set": {"_chain.valid_to": self._cursor.order_key}},
            session=self._session,
        )

        # Step 2. Insert the new document.
        # Insert only if the existing document exists or if upsert.
        if existing is not None or upsert:
            await self.insert_one(collection, replacement)

        return existing

    async def find_one_and_update(
        self, collection: str, filter: DocumentFilter, update: Update
    ):
        """Update the first document in `collection` matching `filter` with `update`."""
        # Step 1. Update the old document (if any) by clamping its validity range
        self._add_current_block_to_filter(filter)
        existing = self._db[collection].find_one_and_update(
            filter,
            {"$set": {"_chain.valid_to": self._cursor.order_key}},
            session=self._session,
        )

        # Step 2. To simulate an update, first insert then call update on it.
        if existing is not None:
            del existing["_id"]
            del existing["_chain"]
            await self.insert_one(collection, existing)
            self._db[collection].update_one(filter, update, session=self._session)

        return existing

    def _add_chain_information(self, doc: Document):
        doc["_chain"] = {"valid_from": self._cursor.order_key, "valid_to": None}