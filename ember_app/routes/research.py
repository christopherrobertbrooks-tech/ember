from fastapi import APIRouter, Depends

from ember_app.auth import get_api_key


router = APIRouter()


@router.get("/api/research")
async def get_research_reports(limit: int = 10, api_key: str = Depends(get_api_key)):
    from tools.research_library import list_research_reports
    return {"reports": list_research_reports(limit=limit)}


@router.get("/api/research/find")
async def find_research(query: str, api_key: str = Depends(get_api_key)):
    from tools.research_library import find_research_report
    return {"result": find_research_report(query)}


@router.get("/api/research/read")
async def read_research(report: str, max_chars: int = 8000, api_key: str = Depends(get_api_key)):
    from tools.research_library import read_research_report
    return {"content": read_research_report(report, max_chars=max_chars)}


@router.get("/api/research/images")
async def research_images(query: str, max_results: int = 8, api_key: str = Depends(get_api_key)):
    from tools.research_library import find_research_images
    return {"images": find_research_images(query, max_results=max_results)}
