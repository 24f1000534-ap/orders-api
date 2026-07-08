from fastapi import FastAPI, Header, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

app = FastAPI()

# -----------------------
# CORS
# -----------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# -----------------------
# CONSTANTS
# -----------------------

TOTAL_ORDERS = 56
RATE_LIMIT = 19
WINDOW = 10  # seconds

# -----------------------
# IN-MEMORY STORAGE
# -----------------------

idempotency_store = {}
client_requests = {}

# Fixed catalog of orders (IDs 1 to 56)
catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# -----------------------
# HOME
# -----------------------

@app.get("/")
def home():
    return {"message": "Orders API is running"}

# -----------------------
# RATE LIMIT MIDDLEWARE
# -----------------------

@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client = request.headers.get("X-Client-Id")

    if client:

        now = time.time()

        if client not in client_requests:
            client_requests[client] = []

        # Keep only requests within the last 10 seconds
        client_requests[client] = [
            t for t in client_requests[client]
            if now - t < WINDOW
        ]

        # Reject if limit exceeded
        if len(client_requests[client]) >= RATE_LIMIT:

            retry_after = max(
                1,
                int(WINDOW - (now - client_requests[client][0])) + 1
            )

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)}
            )

        client_requests[client].append(now)

    response = await call_next(request)
    return response

# -----------------------
# IDEMPOTENT ORDER CREATION
# -----------------------

@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(...)):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order

# -----------------------
# CURSOR PAGINATION
# -----------------------

@app.get("/orders")
def get_orders(limit: int = 10, cursor: str = None):

    if limit < 1:
        limit = 1

    if cursor is None:
        start = 0
    else:
        try:
            start = int(cursor)
        except ValueError:
            start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = str(end)

    return {
        "items": items,
        "next_cursor": next_cursor
    }
