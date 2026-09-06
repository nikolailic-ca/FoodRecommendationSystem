from fastapi import FastAPI

from .routers.recipes import router as recipes_router
from .routers.users import router as users_router
from .routers.auth import router as auth_router

from .auth_database import init_database

from .routers.recommendations import router as recommendations_router

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="Food Recommendation System API",
    description="Backend API for the food recommendation system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_database()

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(recipes_router)
app.include_router(recommendations_router)


@app.get("/")
def root():
    return {
        "message": "Food Recommendation System API is running!"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }