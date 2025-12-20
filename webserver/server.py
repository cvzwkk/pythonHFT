from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pyngrok import ngrok
import uvicorn
import os
import shutil

BASE_DIR = "/tmp/"
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI()

# =========================
# FILE LIST + UPLOAD FORM
# =========================
@app.get("/", response_class=HTMLResponse)
def index():
    files = os.listdir(BASE_DIR)
    file_links = "".join(
        f'<li><a href="/download/{f}">{f}</a></li>' for f in files
    )

    return f"""
    <h2>Upload file</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input type="submit">
    </form>

    <h2>Available files</h2>
    <ul>{file_links}</ul>
    """

# =========================
# UPLOAD
# =========================
@app.post("/upload")
def upload(file: UploadFile = File(...)):
    dest = os.path.join(BASE_DIR, file.filename)

    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"status": "uploaded", "file": file.filename}

# =========================
# DOWNLOAD
# =========================
@app.get("/download/{filename}")
def download(filename: str):
    path = os.path.join(BASE_DIR, filename)

    if not os.path.isfile(path):
        raise HTTPException(status_code=404)

    return FileResponse(path, filename=filename)

# =========================
# START SERVER + NGROK
# =========================
if __name__ == "__main__":
    public_url = ngrok.connect(8008)
    print("Public URL:", public_url)
    uvicorn.run(app, host="0.0.0.0", port=8008)
