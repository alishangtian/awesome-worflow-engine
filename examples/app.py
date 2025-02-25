from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

class ChatRequest(BaseModel):
    input: str

app = FastAPI()

@app.post("/chat")
async def chat(request: ChatRequest):
    if not request.input:
        raise HTTPException(status_code=400, detail="Input text is required.")
    # Simulate AI response using a placeholder (replace with real model inference)
    response_text = f"AI response to: {request.input}"
    return {"response": response_text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)