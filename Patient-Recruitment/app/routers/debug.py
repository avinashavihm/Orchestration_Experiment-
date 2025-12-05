# from fastapi import APIRouter, UploadFile, File, HTTPException
# #from ..services.criteria_extractor import extract_criteria_with_debug
#
# router = APIRouter()
#
# @router.post("/debug/criteria")
# async def debug_criteria(
#     protocol_pdf: UploadFile = File(...),
#     start_page: int | None = None,
#     end_page: int | None = None,
# ):
#     try:
#         pdf_bytes = await protocol_pdf.read()
#         diag = extract_criteria_with_debug(
#             pdf_bytes=pdf_bytes,
#             start_page=start_page,
#             end_page=end_page,
#         )
#         return diag
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Debug failed: {e}")
