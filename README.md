# Template Change Notifications for AAS Submodel Templates

Prototype and validation harness of the paper *"Template Change Notification: Propagating Submodel Template Evolution to Asset Administration Shell Instances"*
(Auer et al., at – Automatisierungstechnik, 2026).

The paper specifies the Template Change Notification (TCN), describes the architecture of this
prototype (§4) and reports the validation (§5). This README explains how to set up and use the
prototype and where the concepts of the paper are implemented.

## Setup

Requires Python 3.13, [uv](https://docs.astral.sh/uv/) and, for the end-to-end cases, Docker.

```bash
uv sync                              # environment from uv.lock
uv run pytest -m "not infra"         # operators, chains, resolution: no Docker needed
docker compose up -d                 # Eclipse BaSyx (Go components, PostgreSQL), RabbitMQ (MQTT), AAS Web UI
uv run pytest -m infra               # end-to-end validation cases V3-V7
```

| Service | Address |
|---|---|
| AAS environment (AAS API v3) | <http://localhost:8081> (container port 8082; set `TCN_AAS_URL` to use another one) |
| AAS Web UI | <http://localhost:3000> |
| RabbitMQ: MQTT, management UI | `localhost:1883`, <http://localhost:15672> |

The image versions are pinned in `docker-compose.yaml`, so that a validation run is reproducible.
The prototype only creates and deletes identifiers below `https://example.com/ids/`; other
content of the environment is left untouched.

> **Pre-configured key.** The BaSyx AAS environment requires an RSA private key
> (`JWS_PRIVATEKEYPATH`). For an easy start, the repository ships a pre-configured **demo key** in
> `basyx/rsa-key.pem`. It is public and must not protect anything beyond a local validation run.
> Replace it with your own key before any other use, e.g.
>
> ```bash
> openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out basyx/rsa-key.pem
> docker compose up -d --force-recreate aas-environment
> ```

The AAS Web UI reads its endpoints from `basyx/basyx-infra.yml` (template `mono-all`: one AAS
environment for all components). The UI stores infrastructures in the browser; after changing the
file, remove the stored infrastructure in the UI settings or clear the site data of
`localhost:3000`.

## Walkthrough

```bash
uv run tcn seed                                                  # AAS of an example device
uv run tcn receive --seconds 60 &                                # asset maintainer receives TCN records via MQTT
uv run tcn owner publish chains/technicaldata_1.2_to_2.0.yaml    # template owner: verify, publish
uv run tcn list                                                  # filed records
uv run tcn preview <NotificationId>                              # effect, conformance and to-do; nothing is written
uv run tcn apply   <NotificationId> --consent                    # new revision of the submodel in the AAS environment
uv run tcn reset                                                 # remove everything below https://example.com/ids/
```

`tcn preview` resolves the record against the current submodel and applies it to a copy; it prints
what the paper lists in §3.4: elided and inserted items, removed and converted values, conformance
to the new template and the to-do list. `--verbose` lists every elided item. `tcn apply` without
`--consent` is rejected.

An applied record yields a new revision of the submodel (`…/rev/2`); the previous revision remains
as baseline. A refused record writes nothing; its reason is set aside in `quarantine/`, and the
record remains waiting.

Delivery via MQTT is a simplification (paper §4.1). Only `src/tcn/infra/broker.py` and
`src/tcn/roles/reception.py` depend on it.

## Authoring a chain

A chain is written as an *intent* file (`chains/*.intent.yaml`) and completed, verified and
published by the template owner (paper §4.1):

```bash
uv run tcn owner complete chains/technicaldata_1.2_to_2.0.intent.yaml chains/technicaldata_1.2_to_2.0.yaml
uv run tcn owner verify   chains/technicaldata_1.2_to_2.0.yaml
uv run tcn owner publish  chains/technicaldata_1.2_to_2.0.yaml
```

Every section of a chain document states its `origin`: `hand`, `rule` or `generated`. The rules
available in `rule` sections are `QualifierTypeRenames`, `RemoveSubtree`, `RemoveChildren` and
`RenameContainer` (`src/tcn/roles/template_owner.py`). Item keys are the argument names of Table 2.
Only verified chains are published.

SMT drop-ins are inserted from the catalogue `ressources/DropIns/catalogue.yaml` (paper §4.2); to
support a further drop-in, add its content there.

`uv run tcn smt <out>` writes the TCN Submodel Template;
`ressources/Templates/Template_TemplateChangeNotification.v0_4.json` is generated this way.

## Structure

| Module | Content | Paper |
|---|---|---|
| `src/tcn/core/model.py` | Decomposition 𝒯 = (𝒯_E, 𝒯_Q, 𝒯_A), assignment functions, derived views, `positions(𝒯)` | §3.2, Fig. 2a |
| `src/tcn/core/metamodel.py` | `adm(t)`, `mand(t)`, container types ℳ_cont for metamodel v3.1.2 | §3.2 |
| `src/tcn/core/operators.py` | The ten atomic operators, each with `pre`, `apply`, `post` and `mod` | §3.2, Table 1 |
| `src/tcn/core/guarded.py` | Guarded application of an operator and of a chain; completion obligation | §3.2 |
| `src/tcn/core/transfer.py` | Transfer functions of `Sync`: Identity, ValueMap, Expression (CEL, allowlisted), Instruction | §3.3, §4.2 |
| `src/tcn/core/addressing.py` | Identification of components by idShort path, qualifier type and attribute key | §3.3, Table 2 |
| `src/tcn/core/matching.py` | Correspondence between a template and a submodel | §3.4 |
| `src/tcn/core/resolution.py` | Resolution of a template chain for one submodel; the complete rules are in its module documentation | §3.4 |
| `src/tcn/core/conformance.py` | Structural conformance of a submodel to a template | §3.4, §6 |
| `src/tcn/dropins.py`, `ressources/DropIns/` | Effective templates | §4.2 |
| `src/tcn/aas/bridge.py` | AAS JSON (via aas-core3.1) ⇄ formal model | §4.1 |
| `src/tcn/aas/tcn_submodel.py` | The TCN Submodel Template and its records | §3.3, Fig. 3 |
| `src/tcn/infra/` | Gateway to the AAS environment, MQTT broker | §4.1, Fig. 4 |
| `src/tcn/roles/` | Template owner, reception, co-evolution | §4.1, Fig. 4 |
| `src/tcn/chainfile.py` | Chain documents (YAML) | §4.1 |
| `src/tcn/cli.py` | Command-line interface of both roles | §4.1 |
| `src/tcn/instantiate.py`, `src/tcn/environment.py` | Instances from templates; the AAS of the example device | §5.1 |
| `chains/` | Intent files and completed chains of the validation | §5 |
| `fixtures/` | Submodel instances of the example device; `fixtures/expected/` the expectations derived by hand | §5.1 |
| `validation/` | Validation harness | §5 |
| `ressources/Templates/` | Published SMTs and the TCN SMT | – |

## Validation

Pass criteria are given in Table 4 of the paper, the results in §5.3 (Tables 5 and 6).

| Case | Test (`validation/`) |
|---|---|
| Operators (Table 1) | `test_operators.py`, with the generic checks of `properties.py` |
| V1, V2 expressiveness | `test_v1_v2_expressiveness.py` |
| V3–V5 transfer of instance values, version gaps | `test_resolution.py` (offline), `test_e2e.py` |
| V6 chain not resolvable | `test_resolution.py`, `test_e2e.py` |
| V7 no change before consent | `test_e2e.py` |
| V8 self-application | `test_v1_v2_expressiveness.py`, `test_resolution.py`, `test_v8_self_application.py` |

`test_e2e.py` requires the Docker environment (`-m infra`); all other tests run offline.

## Open-source software and content used

The prototype builds on the following projects. Their licenses are those stated by the projects
themselves; the Python packages are pinned in `uv.lock`.

**Python packages (runtime)**

| Project | Used for | License |
|---|---|---|
| [aas-core3.1-python](https://github.com/aas-core-works/aas-core3.1-python) | parsing, serialising and verifying AAS models (metamodel v3.1) | MIT |
| [cel-python](https://github.com/cloud-custodian/cel-python) | evaluating CEL expressions of transfer functions | Apache-2.0 |
| [Eclipse Paho MQTT Python Client](https://github.com/eclipse-paho/paho.mqtt.python) | delivery of TCN records | EPL-2.0 OR BSD-3-Clause |
| [Requests](https://github.com/psf/requests) | access to the AAS API | Apache-2.0 |
| [PyYAML](https://github.com/yaml/pyyaml) | chain and fixture documents | MIT |

Indirect dependencies: [lark](https://github.com/lark-parser/lark) (MIT),
[google-re2](https://github.com/google/re2) (BSD-3-Clause), [jmespath](https://github.com/jmespath/jmespath.py) (MIT),
[pendulum](https://github.com/python-pendulum/pendulum) (MIT), [python-dateutil](https://github.com/dateutil/dateutil)
(Apache-2.0 OR BSD-3-Clause), [tzdata](https://github.com/python/tzdata) (Apache-2.0),
[six](https://github.com/benjaminp/six) (MIT), [urllib3](https://github.com/urllib3/urllib3) (MIT),
[certifi](https://github.com/certifi/python-certifi) (MPL-2.0), [charset-normalizer](https://github.com/jawah/charset_normalizer) (MIT),
[idna](https://github.com/kjd/idna) (BSD-3-Clause).

**Development**: [uv](https://github.com/astral-sh/uv) (Apache-2.0 OR MIT), [pytest](https://github.com/pytest-dev/pytest) (MIT).

**Validation environment** (Docker images, run but not distributed with this repository)

| Project | Role | License |
|---|---|---|
| [Eclipse BaSyx Go Components](https://github.com/eclipse-basyx/basyx-go-components) (AAS environment, configuration service) | AAS repository and API of the asset maintainer | MIT |
| [Eclipse BaSyx AAS Web UI](https://github.com/eclipse-basyx/basyx-aas-web-ui) | inspecting submodels and revisions | MIT |
| [RabbitMQ](https://github.com/rabbitmq/rabbitmq-server) | MQTT broker | MPL-2.0 |
| [PostgreSQL](https://www.postgresql.org) | storage backend of BaSyx | PostgreSQL License |

**Specifications and content**

| Content | Source | License |
|---|---|---|
| Submodel Templates IDTA 02003 Technical Data v1.2, v2.0, IDTA 02006 Digital Nameplate v2.0, v3.0 and IDTA 02002 Contact Information v1.0 (source of the drop-in Address Information) in `ressources/Templates/` | [IDTA submodel-templates](https://github.com/admin-shell-io/submodel-templates) | CC BY 4.0, © Industrial Digital Twin Association |
| ZVEI Digital Nameplate v1.0 (`ressources/Templates/SMT_qualified_ZVEI_Digital_Nameplate_V10.json`) | [IDTA submodel-templates, `deprecated/ZVEI_Digital_Nameplate/1/0`](https://github.com/admin-shell-io/submodel-templates/tree/main/deprecated/ZVEI_Digital_Nameplate/1/0) | CC BY 4.0, published by ZVEI and Plattform Industrie 4.0 |
| Common Expression Language | [cel-spec](https://github.com/google/cel-spec) | Apache-2.0 |
| AAS metamodel, API | [IDTA-01001](https://industrialdigitaltwin.org/en/content-hub/aasspecifications), IDTA-01002 | – |

## License

| Part | License | Copyright |
|---|---|---|
| Source code (`src/`, `validation/`) | [MIT](LICENSE) | © 2026 Karlsruhe Institute of Technology (KIT), Institute of Control Systems |
| TCN Submodel Template (`ressources/Templates/Template_TemplateChangeNotification.*.json`), chains (`chains/`), fixtures (`fixtures/`) | [CC BY 4.0](LICENSES/CC-BY-4.0.txt) | © 2026 Karlsruhe Institute of Technology (KIT), Institute of Control Systems |
| Published Submodel Templates (`ressources/Templates/`, all other files) | [CC BY 4.0](LICENSES/CC-BY-4.0.txt) | © Industrial Digital Twin Association (IDTA); ZVEI Digital Nameplate v1.0: ZVEI and Plattform Industrie 4.0. Redistributed unchanged from [admin-shell-io/submodel-templates](https://github.com/admin-shell-io/submodel-templates) |
