from typing import List, Tuple, Annotated

from fastapi import (
  FastAPI,
  status,
  Depends,
  HTTPException,
  Query,
  Request
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models.database import get_database, sqlalchemy_engine
from app.models.models import (
    metadata,
    PostDB,
    PostCreate,
    posts,
    PostPartialUpdate
)
from databases import Database

import logging


logger = logging.getLogger(__name__)


app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_body = await request.body()
    logger.debug(f"Validation error for request: {request.url}")
    logger.debug(f"Request content: {request_body.decode('utf-8')}")
    logger.debug(f"Validation error details: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.on_event("startup")
async def startup():
    await get_database().connect()
    metadata.create_all(sqlalchemy_engine)

@app.on_event("shutdown")
async def shutdown():
    await get_database().disconnect()

@app.get("/")
async def home():
    logger.debug("hello from home debug")
    logger.info("hello from home info")
    return {"hello": "world"}

async def pagination(
    skip: int = Query(0, ge=0),
    limit: int =  Query(10, ge=0),
) -> Tuple[int, int]:
    capped_limit = min(100, limit)
    return (skip, capped_limit)

async def get_post_or_404(id: int, database: Database = Depends(get_database)) -> PostDB:
    select_query = posts.select().where(posts.c.id == id)
    raw_post = await database.fetch_one(select_query)

    if raw_post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return PostDB(**raw_post)


@app.post("/posts", response_model=PostDB, status_code=status.HTTP_201_CREATED)
async def create_post(
        post: PostCreate, database: Database = Depends(get_database)
) -> PostDB:

    logger.info(f"Got a create post request with: {post}")

    insert_query = posts.insert().values(post.dict())
    post_id = await database.execute(insert_query)
    post_db = await get_post_or_404(post_id, database)

    return post_db


@app.get("/posts")
async def list_posts(
        pagination: Tuple[int, int] = Depends(pagination),
        database: Database = Depends(get_database),
) -> List[PostDB]:
    skip, limit = pagination
    select_query = posts.select().offset(skip).limit(limit)
    rows = await database.fetch_all(select_query)

    results = [PostDB(**row) for row in rows]

    logger.info(f"Got results: {results}")
    return results

@app.get("/posts/{id}", response_model=PostDB)
async def get_post(post: PostDB = Depends(get_post_or_404)) -> PostDB:
    return post



@app.get("/posts2")
async def get_my_posts(
      skip: int = 0,
      limit: int = 10,
      database: Database = Depends(get_database),
    ):
    # These are interpreted as ...:8000/?skip=0&limit=10
    logger.info(f"Got: {skip} and {limit}")
    select_query = posts.select()
    rows = await database.fetch_all(select_query)

    results = [PostDB(**row) for row in rows]
    return results


async def common_parameters(
        q: str = "ab",
        skip: int = 10,
        limit: int = 100
      ):
    return {
        "q": q,
        "skip": skip,
        "limit": limit
    }


@app.get("/items")
async def read_items(commons: Annotated[dict, Depends(common_parameters)]):
    return commons

@app.get("/users")
async def read_users(commons: Annotated[dict, Depends(common_parameters)]):
    return commons