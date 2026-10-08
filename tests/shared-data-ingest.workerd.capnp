using Workerd = import "/workerd/workerd.capnp";

# Local runtime regression only: no sockets, credentials, storage or deployment.
const config :Workerd.Config = (
  services = [
    (name = "ingest-runtime-tests", worker = (
      compatibilityDate = "2026-03-17",
      modules = [
        (name = "test.mjs", esModule = embed "shared-data-ingest.workerd.mjs"),
        (name = "worker.mjs", esModule = embed "../services/shared-data-ingest/worker.mjs")
      ]
    )),
    (name = "internet", network = (allow = []))
  ]
);
