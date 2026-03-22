const fs = require("node:fs");
const process = require("node:process");

const { AsyncLocalStorageContextManager } = require("@opentelemetry/context-async-hooks");
const {
  CompositePropagator,
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
} = require("@opentelemetry/core");
const { registerInstrumentations } = require("@opentelemetry/instrumentation");
const { FastifyInstrumentation } = require("@opentelemetry/instrumentation-fastify");
const { HttpInstrumentation } = require("@opentelemetry/instrumentation-http");
const { UndiciInstrumentation } = require("@opentelemetry/instrumentation-undici");
const { resourceFromAttributes } = require("@opentelemetry/resources");
const { NodeTracerProvider } = require("@opentelemetry/sdk-trace-node");
const { ATTR_SERVICE_NAME } = require("@opentelemetry/semantic-conventions");

const APP_BIND = process.env.APP_BIND ?? "0.0.0.0";
const APP_PORT = Number.parseInt(process.env.APP_PORT ?? "9443", 10);
const APP_CERT_FILE = process.env.APP_CERT_FILE;
const APP_KEY_FILE = process.env.APP_KEY_FILE;
const APP_NAME = process.env.APP_NAME;
const DOWNSTREAM_URL = process.env.DOWNSTREAM_URL;
const DOWNSTREAM_NAME = process.env.DOWNSTREAM_NAME;

if (!APP_CERT_FILE || !APP_KEY_FILE || !APP_NAME) {
  throw new Error("APP_CERT_FILE, APP_KEY_FILE, and APP_NAME are required");
}

const provider = new NodeTracerProvider({
  resource: resourceFromAttributes({
    [ATTR_SERVICE_NAME]: APP_NAME,
  }),
});

provider.register({
  contextManager: new AsyncLocalStorageContextManager(),
  propagator: new CompositePropagator({
    propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
  }),
});

registerInstrumentations({
  instrumentations: [
    new HttpInstrumentation(),
    new FastifyInstrumentation(),
    new UndiciInstrumentation(),
  ],
});

const fastify = require("fastify");

const app = fastify({
  https: {
    cert: fs.readFileSync(APP_CERT_FILE, "utf8"),
    key: fs.readFileSync(APP_KEY_FILE, "utf8"),
  },
  logger: false,
});

app.get("/", async (_req, reply) => {
  if (!DOWNSTREAM_URL) {
    return {
      service: APP_NAME,
      message: `hello from ${APP_NAME}`,
    };
  }

  try {
    const response = await fetch(DOWNSTREAM_URL, {
      method: "GET",
      headers: {
        accept: "application/json",
      },
      signal: AbortSignal.timeout(10_000),
    });

    if (!response.ok) {
      throw new Error(`received status ${response.status}`);
    }

    return {
      service: APP_NAME,
      message: `${APP_NAME} called ${DOWNSTREAM_NAME}`,
      downstream: await response.json(),
    };
  } catch (error) {
    reply.code(502);
    return {
      service: APP_NAME,
      error: `downstream request failed: ${error.message}`,
    };
  }
});

app.listen({ host: APP_BIND, port: APP_PORT }).catch((error) => {
  app.log.error(error);
  process.exit(1);
});
