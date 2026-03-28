from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session


class PaginationParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limit = limit
        self.offset = offset
