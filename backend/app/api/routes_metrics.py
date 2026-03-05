from fastapi import APIRouter, Response

from app.core.observability import metrics_registry

router = APIRouter()


@router.get('/metrics')
def metrics() -> Response:
    payload = metrics_registry.render_prometheus()
    return Response(content=payload, media_type='text/plain; version=0.0.4')
