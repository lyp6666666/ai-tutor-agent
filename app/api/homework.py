from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.schema.homework import HomeworkGradeResponse

router = APIRouter(tags=["homework"])


@router.post("/homework/grade_text", response_model=HomeworkGradeResponse)
async def grade_text(
    request: Request,
    session_id: str = Form(...),
    student_id: str = Form(...),
    student_answer: str = Form(...),
    standard_answer: str = Form(...),
) -> HomeworkGradeResponse:
    ctx = request.app.state.ctx
    result = await ctx.dispatcher.grader.grade_text(student_answer, standard_answer)
    return HomeworkGradeResponse(ok=True, session_id=session_id, student_id=student_id, result=result)


@router.post("/homework/grade_image", response_model=HomeworkGradeResponse)
async def grade_image(
    request: Request,
    session_id: str = Form(...),
    student_id: str = Form(...),
    standard_answer: str = Form(...),
    image: UploadFile = File(...),
) -> HomeworkGradeResponse:
    ctx = request.app.state.ctx
    img = await image.read()
    result = await ctx.dispatcher.grader.grade_image(img, standard_answer)
    return HomeworkGradeResponse(ok=True, session_id=session_id, student_id=student_id, result=result)

