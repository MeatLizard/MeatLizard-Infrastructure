"""
Landing page and user registration frontend routes.
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.dependencies import get_db

router = APIRouter(tags=["frontend"])
templates = Jinja2Templates(directory="server/web/app/templates")

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Main landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """User registration page."""
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """User login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """User dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/features", response_class=HTMLResponse)
async def features_page(request: Request):
    """Features overview page."""
    return templates.TemplateResponse("features.html", {"request": request})

@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Pricing and tiers page."""
    return templates.TemplateResponse("pricing.html", {"request": request})

@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    """Documentation page."""
    return templates.TemplateResponse("docs.html", {"request": request})

@router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """System status page."""
    return templates.TemplateResponse("status.html", {"request": request})