from __future__ import annotations

import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


def configure_observability(app) -> None:
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment=settings.environment,
            send_default_pii=False,
        )

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {"service.name": settings.otel_service_name}
        )
        provider = TracerProvider(resource=resource)
        if settings.otel_exporter_otlp_endpoint:
            provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=settings.otel_exporter_otlp_endpoint
                    )
                )
            )

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)

        from app.db.session import engine
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    except Exception:
        logger.exception("Failed to initialize OpenTelemetry")
