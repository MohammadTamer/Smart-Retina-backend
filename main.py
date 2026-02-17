from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import models
from app.db.database import engine
from app.api import auth
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Retina API",
    description="Backend for Retinal Disease Detection",
    version="1.0.0"
)

# CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://smartretina.vercel.app/",

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the other routers
app.include_router(auth.router,prefix="/auth")
@app.get("/")
def read_root():
    return {"message": "Smart Retina API is Online", "status": "Running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}