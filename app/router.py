"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""

from fastapi import APIRouter

from app.controllers.v1 import llm, video
from app.controllers.v1 import channel, job, scheduler_controller, youtube_controller, config_controller
from app.controllers.v1 import intelligence

root_api_router = APIRouter()
# v1 — existing
root_api_router.include_router(video.router)
root_api_router.include_router(llm.router)
# v1 — content farm platform
root_api_router.include_router(channel.router)
root_api_router.include_router(job.router)
root_api_router.include_router(scheduler_controller.router)
root_api_router.include_router(youtube_controller.router)
root_api_router.include_router(config_controller.router)
# v1 — extreme mode intelligence
root_api_router.include_router(intelligence.router)
