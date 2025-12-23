from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pyngrok import ngrok, conf
import uvicorn
import os
import shutil

# =========================
# CONFIG
# =========================
NGROK_AUTH_TOKEN = "37008jtAxiSWPEdzp7OtNvmXcxv_55UUkotksc7ztTYaM2huH"
PORT = 8008
BASE_DIR = "/tmp/"

# Apply ngrok auth token
conf.get_default().auth_token = NGROK_AUTH_TOKEN

os.makedirs(BASE_DIR, exist_ok=True)
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    files = os.listdir(BASE_DIR)
    links = "".join(f'<li><a href="/download/{f}">{f}</a></li>' for f in files)
    return f"""
    <h2>Upload</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input type="submit">
    </form>
    <h2>Files</h2>
    <ul>{links}</ul>
    """

@app.post("/upload")
def upload(file: UploadFile = File(...)):
    path = os.path.join(BASE_DIR, file.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"uploaded": file.filename}

@app.get("/download/{filename}")
def download(filename: str):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, filename=filename)

if __name__ == "__main__":
    public_url = ngrok.connect(PORT)
    print("Public URL:", public_url)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
