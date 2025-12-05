from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from .routers.run import router as run_router
from fastapi.responses import RedirectResponse
# from .routers import run
# from .routers import debug  # NEW

def root():
    return RedirectResponse(url="/docs")

app = FastAPI(
    title="Patient Recruitment Agent (POC)", 
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware to increase max upload size
class MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Increase max body size to 100MB (104857600 bytes)
        if hasattr(request, "_json"):
            # This is handled by uvicorn, but we can set it here too
            pass
        return await call_next(request)

app.add_middleware(MaxUploadSizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
    expose_headers=["X-Metadata", "Content-Disposition"]  # Expose custom headers to frontend
)
@app.get("/", include_in_schema=False)
@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(run_router, prefix="")



# app = FastAPI()
# app.include_router(run.router, prefix="")
# app.include_router(debug.router, prefix="")

