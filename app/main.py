from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Quittung API")


@app.get("/health")
async def health_check():
    return {"status": "online", "message": "Quittung API is running"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
