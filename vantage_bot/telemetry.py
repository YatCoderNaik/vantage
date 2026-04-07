import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from google.cloud import logging as cloud_logging

# Global tracer
tracer = trace.get_tracer("vantage-bot")

def setup_telemetry():
    """Configures OpenTelemetry and Cloud Logging for the Vantage Bot."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("⚠️ GOOGLE_CLOUD_PROJECT not set. Telemetry/Logging limited.")
        return

    # 1. Setup Resource
    resource = Resource.create({
        "service.name": "vantage-assistant",
        "service.namespace": "hackathon",
        "project.id": project_id
    })

    # 2. Setup Tracer Provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # 3. Setup Tracing Exporter
    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        exporter = CloudTraceSpanExporter(project_id=project_id)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        print(f"✅ OpenTelemetry configured: Cloud Trace (Project: {project_id})")
    except ImportError:
        print("⚠️ CloudTraceSpanExporter not found.")

    # 4. Setup Cloud Logging
    try:
        log_client = cloud_logging.Client(project=project_id)
        log_client.setup_logging()
        print(f"✅ Cloud Logging configured (Project: {project_id})")
    except Exception as e:
        print(f"⚠️ Cloud Logging setup failed: {e}")

    # 5. Enable ADK detailed tracing
    os.environ["ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS"] = "True"

def get_tracer():
    return tracer
