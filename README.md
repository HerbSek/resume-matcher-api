# Resume Matcher API

A FastAPI application that provides API endpoints for matching resumes to job descriptions, optimized for deployment to Render or via Docker.

## Features

- Extract text from PDF resumes
- Process job descriptions from scraped content
- Match resumes to job descriptions using AI
- Generate tailored resumes in JSON format
- Improved error handling and validation
- Comprehensive API documentation

## API Endpoints

- `GET /`: Root endpoint
- `GET /health`: Health check endpoint
- `POST /extract-resume`: Extract text from a resume file
- `POST /match`: Match resume text to job description
- `POST /match-from-url-and-file`: Match resume file to job URL
- `POST /process-scraped-job`: Process a job description scraped from a website

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Groq API key
- Docker (optional, for containerized deployment)

### Option 1: Local Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd mvp1_api
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Create a `.env` file with the following variables:
   ```
   PORT=8000
   HOST=0.0.0.0
   GROQ_API_KEY=your_groq_api_key
   MODEL_NAME=llama-3.3-70b-versatile
   ```

6. Start the API server:
   ```
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

7. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Option 2: Docker Deployment

1. Make sure Docker is installed on your system

2. Create a `.env` file with your Groq API key:
   ```
   GROQ_API_KEY=your_groq_api_key
   ```

3. Build and run the Docker container:
   ```
   # Build the Docker image
   docker build -t resume-matcher-api .

   # Run the container
   docker run -p 8000:8000 --env-file .env resume-matcher-api
   ```

   Alternatively, use Docker Compose:
   ```
   docker-compose up --build
   ```

4. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Usage Examples

### Extract Resume Text

```python
import requests

url = "http://localhost:8000/extract-resume"
files = {"resume_file": open("resume.pdf", "rb")}

response = requests.post(url, files=files)
print(response.json())
```

### Process Scraped Job Description

```python
import requests
import json

url = "http://localhost:8000/process-scraped-job"
payload = {
    "job_description": "We are looking for a Software Engineer with experience in Python..."
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)
print(json.dumps(response.json(), indent=2))
```

### Match Resume to Job

```python
import requests
import json

url = "http://localhost:8000/match"
payload = {
    "resume_text": "Your resume text here...",
    "job_description": "Job description text here..."
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=payload, headers=headers)
print(json.dumps(response.json(), indent=2))
```

### Match Resume File to Job URL

```python
import requests
import json

url = "http://localhost:8000/match-from-url-and-file"
files = {"resume_file": open("resume.pdf", "rb")}
data = {"job_url": "https://example.com/job-posting"}

response = requests.post(url, files=files, data=data)
print(json.dumps(response.json(), indent=2))
```

## Deployment Options

### Option 1: Deploy to Render

#### Direct Upload (No GitHub Required)

1. Zip your project files (exclude venv, __pycache__, etc.)
2. Log in to Render (https://render.com)
3. Click "New" and select "Web Service"
4. Choose "Upload" instead of connecting to a Git repository
5. Upload your zip file
6. Configure the service:
   - Name: resume-matcher-api
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Add environment variables:
   - `GROQ_API_KEY`: Your Groq API key
   - `MODEL_NAME`: llama-3.3-70b-versatile
8. Click "Create Web Service"

#### Using Render CLI

1. Install the Render CLI: `npm install -g render`
2. Login to Render: `render login`
3. Initialize your project: `render init`
4. Deploy your service: `render deploy`

### Option 2: Deploy with Docker to Any Cloud Provider

1. Build the Docker image: `docker build -t resume-matcher-api .`
2. Push the image to a container registry (Docker Hub, AWS ECR, Google Container Registry, etc.)
3. Deploy the container to your preferred cloud provider (AWS, GCP, Azure, etc.)
4. Make sure to set the `GROQ_API_KEY` environment variable

## Testing the Deployed API

Once deployed, you can test the API using the following endpoints:

- Swagger UI: https://your-deployed-url/docs
- Health Check: https://your-deployed-url/health

## License

This project is licensed under the MIT License - see the LICENSE file for details.
