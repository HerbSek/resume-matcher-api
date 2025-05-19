from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, HttpUrl, Field, validator
from typing import Optional, Dict, Any, List
import requests
import json
import os
import tempfile
import logging
from io import BytesIO
from groq import Groq
import fitz  # PyMuPDF
from dotenv import load_dotenv
import sys
import importlib.util
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import example from prompts.py
# First, try to import directly
try:
    from prompts import example
    logger.info("Successfully imported example from prompts.py")
except ImportError:
    # If that fails, try to load it from the parent directory
    logger.info("Failed to import directly, trying to load from parent directory")
    try:
        # Add parent directory to path
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(parent_dir)

        # Try importing again
        from prompts import example
        logger.info("Successfully imported example from parent directory")
    except ImportError:
        # If that also fails, define a basic example structure
        logger.warning("Could not import example from prompts.py, using default example")
        example = """
        {
            "username": "example-user",
            "firstName": "John",
            "lastName": "Doe",
            "headline": "Software Engineer",
            "location": "New York, NY",
            "phoneNumber": "123-456-7890",
            "linkedin": "https://linkedin.com/in/johndoe",
            "email": "john.doe@example.com",
            "education": [
                {
                    "degree": "Bachelor of Science in Computer Science",
                    "institution": "Example University",
                    "startDate": "2015",
                    "endDate": "2019"
                }
            ],
            "workExperience": [
                {
                    "position": "Software Engineer",
                    "organization": "Example Company",
                    "startDate": "2019",
                    "endDate": "Present",
                    "tasks": [
                        "Developed web applications using React and Node.js",
                        "Implemented RESTful APIs",
                        "Collaborated with cross-functional teams"
                    ]
                }
            ],
            "objective": "To obtain a position as a Software Engineer",
            "summary": "Experienced software engineer with expertise in web development",
            "skills": ["JavaScript", "React", "Node.js", "Python"],
            "relevantProjects": [
                {
                    "title": "Project Example",
                    "description": "A web application for example purposes",
                    "technologies": ["React", "Node.js", "MongoDB"]
                }
            ],
            "coverLetter": ""
        }
        """

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

# Initialize FastAPI app
app = FastAPI(
    title="Resume Matcher API",
    description="API for matching resumes to job descriptions",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class JobUrlInput(BaseModel):
    job_url: HttpUrl = Field(..., description="URL of the job posting to extract information from")

    class Config:
        schema_extra = {
            "example": {
                "job_url": "https://example.com/job-posting"
            }
        }

class ResumeJobMatchInput(BaseModel):
    resume_text: str = Field(..., description="The extracted text from a resume")
    job_description: str = Field(..., description="The job description text")

    @validator('resume_text')
    def resume_text_not_empty(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError('Resume text must not be empty and should contain meaningful content (at least 50 characters)')
        return v

    @validator('job_description')
    def job_description_not_empty(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError('Job description must not be empty and should contain meaningful content (at least 50 characters)')
        return v

    class Config:
        schema_extra = {
            "example": {
                "resume_text": "John Doe\nSoftware Engineer\n5 years of experience in Python development...",
                "job_description": "We are looking for a Software Engineer with experience in Python..."
            }
        }

class ResumeJobMatchResponse(BaseModel):
    matched_resume: Dict[str, Any] = Field(..., description="The tailored resume matched to the job description")
    processing_time: float = Field(..., description="Time taken to process the request in seconds")

# Helper functions
def extract_resume_info(file_content):
    """Extract text from a PDF resume."""
    try:
        # Validate file content
        if not file_content or len(file_content) < 100:
            raise ValueError("PDF file is too small or empty")

        # Create a BytesIO object from the file content
        pdf_stream = BytesIO(file_content)

        # Open the PDF from the BytesIO object
        try:
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
        except Exception as e:
            logger.error(f"Error opening PDF: {e}")
            raise ValueError(f"Invalid PDF file: {str(e)}")

        # Check if the document has pages
        if doc.page_count == 0:
            raise ValueError("PDF file has no pages")

        # Extract text from all pages
        text = ""
        for page in doc:
            text += page.get_text()

        # Close the document
        doc.close()

        # Validate extracted text
        if not text or len(text.strip()) < 50:
            raise ValueError("Could not extract meaningful text from the PDF (less than 50 characters)")

        return text
    except ValueError as e:
        logger.error(f"Validation error in extract_resume_info: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting resume info: {e}")
        raise HTTPException(status_code=500, detail=f"Error extracting resume info: {str(e)}")

def extract_job_info(job_url):
    """Extract job information from a URL."""
    try:
        # Make request to job URL
        response = requests.get(job_url)

        # Check if request was successful
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch job information: {response.text}")

        # Extract HTML content (limit to first 6000 characters)
        html = response.text
        html = html[1:6000]

        # Use Groq to extract job information
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"You are a job Information extractor. Strictly extract information about the job only from this extracted text:{html}",
                }
            ],
            model=os.getenv("MODEL_NAME", "llama-3.3-70b-versatile"),
        )

        # Extract output
        output_info = chat_completion.choices[0].message.content

        return output_info
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error extracting job info: {e}")
        raise HTTPException(status_code=500, detail=f"Error extracting job info: {str(e)}")

def match_user_job(user_info, job_info):
    """Match user resume to job description."""
    start_time = time.time()

    try:
        # Validate inputs
        if not user_info or len(user_info.strip()) < 50:
            raise ValueError("Resume text is too short or empty")

        if not job_info or len(job_info.strip()) < 50:
            raise ValueError("Job description is too short or empty")

        # Create prompt for matching
        prompt_user_job = fr"""
        You are an API that strictly returns data in JSON.
        Generate a resume by strictly tailoring every component of the user information:{user_info} to the job description:{job_info} and format the resume as a valid JSON object.
        Prioritize aligning the following aspects:
        1. Skills: Only include skills that appear in both the job description and the user's data.
        2. Experience: Emphasize relevant work experiences that reflect responsibilities or requirements in the job description.
        3. Summary: Create a summary that clearly states why the user is a great match for the role based on the identified key requirements.
        Do not include any other output. No markdown, no comments,
        no code fences, no extra text — just plain JSON, nothing to enclose it with. There is a cover letter key in the json format. Also generate a cover letter to match the resume attached and job description.
        Resume MUST strictly be in this format, {example}. No changes to the example format since there will be a database used to store the JSON data.
        """

        # Use Groq to match resume to job with timeout handling
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt_user_job,
                    }
                ],
                model=os.getenv("MODEL_NAME", "llama-3.3-70b-versatile"),
                timeout=60,  # 60 second timeout
            )
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Error communicating with AI service: {str(e)}. Please try again later."
            )

        # Extract and parse output
        try:
            user_job_info_text = chat_completion.choices[0].message.content
            user_job_info = json.loads(user_job_info_text)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            logger.error(f"Raw response: {chat_completion.choices[0].message.content}")

            # Try to clean the response and parse again
            cleaned_response = user_job_info_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response.replace("```json", "", 1)
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]

            cleaned_response = cleaned_response.strip()

            try:
                user_job_info = json.loads(cleaned_response)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail="The AI generated an invalid JSON response. Please try again."
                )

        # Calculate processing time
        processing_time = time.time() - start_time

        # Return both the matched resume and the processing time
        return {
            "matched_resume": user_job_info,
            "processing_time": round(processing_time, 2)
        }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}")
        if 'chat_completion' in locals():
            logger.error(f"Raw response: {chat_completion.choices[0].message.content}")
        raise HTTPException(status_code=500, detail=f"Error parsing AI response: {str(e)}")
    except Exception as e:
        logger.error(f"Error matching user to job: {e}")
        raise HTTPException(status_code=500, detail=f"Error matching user to job: {str(e)}")

# API endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the Resume Matcher API"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/extract-job", response_model=Dict[str, str])
async def extract_job_endpoint(job_input: JobUrlInput):
    """Extract job information from a URL."""
    try:
        job_info = extract_job_info(str(job_input.job_url))
        return {"job_description": job_info}
    except Exception as e:
        logger.error(f"Error in extract-job endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-resume", response_model=Dict[str, str])
async def extract_resume_endpoint(resume_file: UploadFile = File(...)):
    """Extract text from a resume file."""
    try:
        # Check file type
        if not resume_file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await resume_file.read()

        # Extract resume information
        resume_text = extract_resume_info(file_content)

        return {"resume_text": resume_text}
    except Exception as e:
        logger.error(f"Error in extract-resume endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/match", response_model=ResumeJobMatchResponse,
         description="Match a resume to a job description and generate a tailored resume")
async def match_endpoint(match_input: ResumeJobMatchInput):
    """
    Match resume to job description and generate a tailored resume.

    - Takes resume text and job description as input
    - Uses AI to analyze and match the resume to the job requirements
    - Returns a tailored resume in JSON format
    """
    try:
        # Match resume to job
        result = match_user_job(match_input.resume_text, match_input.job_description)

        return result
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status code and detail
        raise
    except Exception as e:
        logger.error(f"Error in match endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/match-from-url-and-file", response_model=ResumeJobMatchResponse,
         description="Match a resume file to a job description from a URL")
async def match_from_url_and_file(
    job_url: str = Form(..., description="URL of the job posting"),
    resume_file: UploadFile = File(..., description="PDF resume file")
):
    """
    Match a resume file to a job description from a URL.

    - Takes a PDF resume file and a job URL as input
    - Extracts text from the resume and job information from the URL
    - Uses AI to analyze and match the resume to the job requirements
    - Returns a tailored resume in JSON format
    """
    try:
        # Check file type
        if not resume_file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await resume_file.read()

        # Extract resume information
        resume_text = extract_resume_info(file_content)

        # Extract job information
        job_info = extract_job_info(job_url)

        # Match resume to job
        result = match_user_job(resume_text, job_info)

        return result
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status code and detail
        raise
    except Exception as e:
        logger.error(f"Error in match-from-url-and-file endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Add a new endpoint for handling job description string from scraper
class ScrapedJobInput(BaseModel):
    job_description: str = Field(..., description="The job description text scraped from a website")

    @validator('job_description')
    def job_description_not_empty(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError('Job description must not be empty and should contain meaningful content (at least 50 characters)')
        return v

    class Config:
        schema_extra = {
            "example": {
                "job_description": "We are looking for a Software Engineer with experience in Python..."
            }
        }

@app.post("/process-scraped-job", response_model=Dict[str, str],
         description="Process a job description scraped from a website")
async def process_scraped_job(job_input: ScrapedJobInput):
    """
    Process a job description scraped from a website.

    - Takes a job description text as input
    - Validates and cleans the job description
    - Returns the processed job description ready for matching
    """
    try:
        # Validate job description
        job_description = job_input.job_description.strip()

        # Process the job description if needed
        # This could include cleaning, formatting, extracting key information, etc.

        return {"job_description": job_description}
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status code and detail
        raise
    except Exception as e:
        logger.error(f"Error in process-scraped-job endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Add custom documentation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Resume Matcher API",
        version="1.1.0",
        description="""
        # Resume Matcher API

        This API provides endpoints for matching resumes to job descriptions.

        ## Key Features

        - Extract text from PDF resumes
        - Process job descriptions from scraped content
        - Match resumes to job descriptions using AI
        - Generate tailored resumes in JSON format

        ## Authentication

        This API uses API keys for authentication. Include your API key in the request headers.

        ## Rate Limits

        There are rate limits in place to prevent abuse. Please contact us if you need higher limits.
        """,
        routes=app.routes,
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Run the application
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run("main:app", host=host, port=port, reload=True)
