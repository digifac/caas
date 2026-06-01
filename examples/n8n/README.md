# n8n Workflows for CAAS

Ready-to-import n8n workflows to integrate CAAS (Conversion as a Service) into your automations.

## 📁 Files

| File                           | Description                                          |
| ------------------------------ | ---------------------------------------------------- |
| `caas-workflow-example.json`   | Simple synchronous conversion (8 formats → Markdown) |
| `caas-workflow-async.json`     | Asynchronous conversion with status polling          |
| `caas-workflow-streaming.json` | Streaming conversion via Server-Sent Events (SSE)    |
| `caas-workflow-batch.json`     | Batch conversion of multiple files                   |

## 🚀 Import into n8n

1. Open n8n in your browser
2. Click **Workflows** → **Import from File** (or use `Ctrl+I` / `Cmd+I`)
3. Select the desired `.json` file
4. Adjust the parameters for your environment

## 🔧 Configuration

### Environment Variables

| Variable   | Default                 | Description  |
| ---------- | ----------------------- | ------------ |
| `CAAS_URL` | `http://localhost:8000` | CAAS API URL |

### HTTP Request Node — CAAS Convert

The core node in each workflow is an **HTTP Request** configured as follows:

```json
{
  "method": "POST",
  "url": "http://localhost:8000/convert",
  "sendFiles": true,
  "fileKey": "file",
  "options": {
    "timeout": 30000
  }
}
```

#### Detailed Parameters

| n8n Parameter     | Value                           | Description                              |
| ----------------- | ------------------------------- | ---------------------------------------- |
| `method`          | `POST`                          | HTTP method                              |
| `url`             | `http://localhost:8000/convert` | CAAS endpoint                            |
| `sendFiles`       | `true`                          | Enable file upload (multipart/form-data) |
| `fileKey`         | `file`                          | Form field name for the file             |
| `options.timeout` | `30000`                         | Timeout in milliseconds                  |

### Conversion Modes

#### Synchronous (default)

```
POST http://localhost:8000/convert
```

Immediate response with the converted Markdown:

```json
{
  "success": true,
  "result": {
    "markdown": "# Titre du document\n\nContenu converti...",
    "filename": "document.pdf",
    "pages": 3
  }
}
```

#### Asynchronous

```
POST http://localhost:8000/convert?async=true
```

Returns a `task_id` for polling:

```json
{
  "success": true,
  "task_id": "a1b2c3d4",
  "status": "pending",
  "message": "Task submitted in the background."
}
```

Then poll the status:

```
GET http://localhost:8000/task/a1b2c3d4
```

#### Streaming

```
POST http://localhost:8000/convert?streaming=true
```

Returns a Server-Sent Events (SSE) stream. Each event contains the accumulated markdown up to that point:

```
data: # Page 1 content\n\nSome text...\n\n
data: # Page 1 content\n\nSome text...\n\n# Page 2 content\n\nMore text...\n\n
```

The last event contains the complete converted document.

**n8n Configuration** — set `responseFormat` to `stream` in the HTTP Request node options:

```json
{
  "method": "POST",
  "url": "http://localhost:8000/convert?streaming=true",
  "sendFiles": true,
  "fileKey": "file",
  "options": {
    "timeout": 60000,
    "responseFormat": "stream"
  }
}
```

#### Batch

```
POST http://localhost:8000/convert/batch
```

Same configuration as the synchronous node, but with `sendFiles: true` and multiple files.

## 📡 CAAS Endpoints

| Method | Endpoint                    | Description                                 |
| ------ | --------------------------- | ------------------------------------------- |
| `POST` | `/convert`                  | Synchronous file conversion                 |
| `POST` | `/convert?async=true`       | Asynchronous conversion (returns task_id)   |
| `POST` | `/convert?streaming=true`   | Streaming conversion via Server-Sent Events |
| `POST` | `/convert/batch`            | Batch conversion of multiple files          |
| `POST` | `/convert/batch?async=true` | Batch async conversion (returns batch_id)   |
| `GET`  | `/task/{task_id}`           | Async task status and result                |
| `GET`  | `/tasks`                    | Queue overview                              |
| `GET`  | `/health`                   | Health check with Redis & task diagnostics  |

## 🔗 Example n8n Chains

### Conversion → Storage

```
[Trigger] → [Read File] → [CAAS Convert] → [Write File (Markdown)]
```

### Conversion → LLM

```
[Trigger] → [Read File] → [CAAS Convert] → [OpenAI / Anthropic / Ollama]
```

### Streaming Conversion → LLM

```
[Trigger] → [Read File] → [CAAS Stream Convert] → [Parse SSE] → [OpenAI / Anthropic / Ollama]
```

### Batch Conversion → Aggregation

```
[Trigger] → [Read Files] → [CAAS Batch Convert] → [Merge] → [Output]
```

## ⚠️ Notes

- Make sure CAAS is reachable from n8n (same network, or exposed URL)
- Default rate limiting is **30 requests/minute** per IP
- Maximum file size is **50 MB** by default
- Supported formats are **PDF**, **DOCX**, **ODT**, **ODP**, **ODS**, **HTML**, **XLSX**, and **PPTX**
- Streaming mode requires `STREAMING_ENABLED=true` in the CAAS environment
