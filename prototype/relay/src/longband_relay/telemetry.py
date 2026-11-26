from __future__ import annotations

import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_enabled = os.environ.get("LONGBAND_OTEL_ENABLED", "0") == "1"
if _enabled:
    provider = TracerProvider(resource=Resource.create({
        "service.name": "longband-alpha",
        "service.version": os.environ.get("LONGBAND_REVISION", "unknown"),
        "longband.environment": "public-alpha",
    }))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:4318/v1/traces")
    )))
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer("longband.relay")


@contextmanager
def operation(name: str, stage: str, *, payload_bytes: int | None = None):
    if not _enabled:
        yield None
        return
    attributes: dict[str, str | int] = {"longband.stage": stage}
    if payload_bytes is not None:
        attributes["longband.payload_bytes"] = payload_bytes
    with tracer.start_as_current_span(
        name, attributes=attributes, record_exception=False, set_status_on_exception=False,
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_attribute("longband.result", "error")
            span.set_attribute("exception.type", type(exc).__name__)
            span.set_status(trace.StatusCode.ERROR)
            raise
        else:
            span.set_attribute("longband.result", "ok")
