sed -i '/name = "prometheus-client"/d' Backend/uv.lock
sed -i '/name = "opentelemetry-api"/d' Backend/uv.lock
sed -i '/name = "opentelemetry-sdk"/d' Backend/uv.lock
sed -i '/name = "opentelemetry-exporter-otlp"/d' Backend/uv.lock
sed -i '/name = "opentelemetry-instrumentation-fastapi"/d' Backend/uv.lock
sed -i '/name = "ddtrace"/d' Backend/uv.lock
