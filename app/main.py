from ctypes import cast
from typing import List, Mapping, Tuple, Annotated

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
    PostDB,
    PostCreate,
    PostPublic,
    PostPartialUpdate,
    CommentBase,
    CommentDB,
    CommentCreate,
    metadata,
    posts,
    comments
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
    select_post_query = posts.select().where(posts.c.id == id)
    raw_post = await database.fetch_one(select_post_query)

    if raw_post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    select_post_comments_query = comments.select().where(comments.c.post_id == id)
    raw_comments = await database.fetch_all(select_post_comments_query)
    comments_list = [CommentDB(**comment) for comment in raw_comments]

    return PostPublic(**raw_post, comments=comments_list)



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


@app.patch("/posts/{id}", response_model=PostDB)
async def update_post(
    post_update: PostPartialUpdate,
    post: PostDB = Depends(get_post_or_404),
    database: Database = Depends(get_database),
) -> PostDB:
    logger.info(f"Patching post: {post.id}")
    logger.info(f"Got: {post}")

    update_query = (
        posts.update()
        .where(posts.c.id == post.id)
        .values(post_update.model_dump(exclude_unset=True))
    )
    await database.execute(update_query)
    post_db = await get_post_or_404(post.id, database)

    return post_db

@app.delete("/posts/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post: PostDB = Depends(get_post_or_404),
    database: Database = Depends(get_database)
):
    delete_query = posts.delete().where(posts.c.id == post.id)
    await database.execute(delete_query)
    return post.id

@app.post("/comments", response_model=CommentDB, status_code=status.HTTP_201_CREATED)
async def create_comment(
    comment: CommentCreate,
    database: Database = Depends(get_database)
) -> CommentDB:
    select_post_query = posts.select().where(posts.c.id == comment.post_id)
    post = await database.fetch_one(select_post_query)

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Post {comment.post_id} does not exist"
        )

    insert_query = comments.insert().values(comment.model_dump())
    comment_id = await database.execute(insert_query)

    select_query = comments.select().where(comments.c.id == comment_id)
    raw_comment = cast(Mapping, await database.fetch_one(select_query))

    return CommentDB(**raw_comment)


@app.get("/comments")
async def list_comments(
    database: Database = Depends(get_database)
) -> List[CommentDB]:
    select_query = comments.select()
    rows = await database.fetch_all(select_query)

    results = [CommentDB(**row) for row in rows]

    logger.info(f"Got results: {results}")
    return results
