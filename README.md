# Open WebUI Vision Caption Filter (Image → Text) via Pipelines

This project provides an **Open WebUI Pipelines FILTER** that enables **image support for text-only LLMs**.

When a user attaches an image in Open WebUI:
1. The filter detects the image in the OpenAI-style request payload.
2. The image is sent to a **vision-capable LLM** (any OpenAI-compatible backend).
3. The vision model returns a **rich textual description**.
4. The image is removed from the request.
5. The description is injected as plain text into the user message.
6. Open WebUI continues by calling the **text-only LLM backend**.

This prevents crashes or errors (for example `mmproj`) on text-only backends while still allowing image-based interaction.

---

## Official documentation
- Open WebUI Pipelines:
  https://docs.openwebui.com/features/pipelines/

---

## Requirements
You need:
- **Open WebUI** running (any supported deployment method).
- **Docker** on the host system.
- A **text model backend** that is **OpenAI API compatible**.
  - Examples: llama.cpp OpenAI server, vLLM OpenAI server, TGI, etc.
  - The backend must be text-only.
- A **vision model backend** that is **OpenAI API compatible**.
  - Must support `image_url` in OpenAI-style `messages`.
  - Example: Qwen3-VL via vLLM.

---

## Architecture
```
User
↓
Open WebUI
↓
Pipelines FILTER (image → caption)
↓
Text-only LLM (OpenAI-compatible)
```
The vision model is never selected directly by the user.

---

## Step-by-step Setup
### 1) Create a pipelines directory on the host
```bash
mkdir -p /home/<user>/pipelines
```

### 2) Start the Open WebUI Pipelines server
```bash
sudo docker rm -f pipelines 2>/dev/null || true

sudo docker run -d   --name pipelines   --restart always   -p 9099:9099   --add-host=host.docker.internal:host-gateway   -e PIPELINES_DIR="/pipelines"   -v /home/<user>/pipelines:/pipelines   ghcr.io/open-webui/pipelines:main
```
Check that the server is running:
```bash
sudo docker logs -f pipelines
```
You should see output similar to:
```
Uvicorn running on http://0.0.0.0:9099
```

### 3) Connect the Pipelines server to Open WebUI
Open WebUI treats the Pipelines server as an **OpenAI-compatible provider**.
In Open WebUI:
1. Go to **Admin Panel → Settings → Connections**
2. Add a new **OpenAI-compatible** connection
| Field | Value |
|------|-------|
| Base URL | `http://host.docker.internal:9099` |
| API Key  | `0p3n-w3bu!` |
3. Save the connection
`host.docker.internal` works because the container was started with:
`--add-host=host.docker.internal:host-gateway`.

### 4) Install the filter script
Copy the pipeline script from this repository into your pipelines directory:
```bash
cp 10_qwen3vl_caption_filter.py /home/<user>/pipelines/10_qwen3vl_caption_filter.py
```
Restart the Pipelines server so the script is loaded:
```bash
sudo docker restart pipelines
sudo docker logs -f pipelines
```
Verify that the pipeline appears as:
```
10_qwen3vl_caption_filter (filter)
```
If it appears as `(pipe)` instead of `(filter)`, the script is incorrect.

### 5) Configure the pipeline (Valves) in Open WebUI
In Open WebUI:
1. Go to **Admin Panel → Settings → Pipelines**
2. Find `10_qwen3vl_caption_filter (filter)`
3. Open **Valves**

#### Apply the filter to models
You can apply the filter to one or multiple Open WebUI model IDs.
Apply to all models:
```json
["*"]
```
Apply to specific models:
```json
["TextModelA", "TextModelB"]
```
Use the exact model IDs as shown in Open WebUI.

#### Configure the vision backend
Example values:
- `qwen_base_url`:
```
http://192.xxx.xxx.xxx:8282
```
- `qwen_model`:
```
vLLMQwen3VL30B
```
If your vision backend requires authentication, set `qwen_api_key`.

### 6) Ensure text models are text-only
For all models this filter applies to:
- Disable **Vision / Image input** in the model configuration.
- The model must be text-only. The filter removes images before the request reaches the backend.

---

## Example caption prompt
The pipeline includes a customizable example prompt:
```
You convert the given image into a rich text in english language.
Return ONLY the final prompt as a single line, no quotes, no extra text.
Include: subject, environment, style, lighting, camera/lens, composition,
key details, ethnicity of people, position and angle of the object in the picture,

detailed clothes description, face description of people, look direction of people,
posture of people, age of people.
All these key description instructions need to be applied on each recognized object,
person, scenery etc. be very detailed and structured in the description.
Avoid meta-commentary.
```
You can freely adapt this prompt for OCR, product descriptions, art analysis, or scene understanding.

---

## Testing
1. Open a chat using a normal **text model**.
2. Attach an image.
3. Send a message.
Expected behavior:
- The filter intercepts the request.
- The image is sent to the vision model.
- The image is removed from the request.
- The generated description is injected as text.
- The text-only backend receives only text input.

---

## Troubleshooting
### Pipeline does not run
- Ensure it is shown as `(filter)` in the Pipelines list.
- Ensure `type = "filter"` exists in the script.
- Ensure the model ID is listed in the `pipelines` valve.

### Vision request fails
Check Pipelines logs:
```bash
sudo docker logs -f pipelines
```
Common issues include:
- Wrong vision backend URL
- Wrong model name
- Missing or invalid API key

### Some images are ignored
The filter processes only:
- `data:image/...` URLs
- URLs ending in common image extensions
Non-image files (PDF, TXT, WAV, etc.) are ignored by design.
