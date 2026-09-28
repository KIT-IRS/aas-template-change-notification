# Template Change Notifications for AAS Submodel Templates

Demonstrator and validation of the paper *"The Old Template is Dead, Long Live the New Template!
Template Change Notifications for Asset Administration Shell Submodel Templates"*
(Auer et al., at – Automatisierungstechnik, 2026).

A Template Change Notification (TCN) describes a revision of a Submodel Template (SMT) as an ordered
chain of atomic change operations. The template owner publishes it; the asset maintainer files it,
previews its effect and applies it to a conforming submodel only upon explicit consent. An operation
that is inadmissible leaves the submodel unchanged.

The code is kept small on purpose: every module corresponds to one concept of the paper, and the
formal model is implemented literally, so that the guarantees can be checked generically.

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
The demonstrator only creates and deletes identifiers below `https://example.com/ids/`; other
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
>
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
uv run tcn preview <NotificationId>                              # preview the effect of the change, conformance and to-do; nothing is written yet
uv run tcn apply   <NotificationId> --consent                    # publish new revision of the submodel in the local AAS environment
uv run tcn reset
```

`tcn preview` resolves the record against the current submodel and applies it to a copy. Nothing
is written; the asset maintainer sees, before consent:

- **values removed**: every value of the submodel the change removes without carrying it over, with
  its path and value, as an explicit warning. By consenting, the asset maintainer accepts their
  removal and keeps them elsewhere if they are still needed;
- **values converted automatically**: every value an executable transfer function converts, before
  and after;
- **conformance**: whether the result conforms to the new template;
- **to do**: every violation of the new template (a mandatory element missing or without value, too
  many realisations, a different value type), every transformation stated as an instruction, and
  every SMT drop-in the new template uses that is not available (see [Drop-ins](#drop-ins)).

Elements the template does not describe, such as local extensions, are kept and listed. After a
consented update, the submodel conforms to the new template, except for the values listed under
*to do*.

An applied record yields a new revision of the submodel (`…/rev/2`); the AAS is redirected to it,
and the previous revision remains unchanged as baseline. A refused record writes nothing; its reason
is set aside in `quarantine/`, and the record remains waiting.

**Delivery via MQTT is a simplification of the demonstrator.** Records are pushed as MQTT events
because this keeps the setup small: one broker, one topic per template family. In an industrial
scenario, the asset maintainer would rather poll the template owner's publication endpoint for new
records, e.g. periodically, so that no broker has to be shared across organisational boundaries
and each asset maintainer decides when to fetch notifications. The TCN records and everything
after their reception are independent of the delivery mechanism; only `src/tcn/infra/broker.py`
and `src/tcn/roles/reception.py` would change.

## Structure

| Module | Content | Paper |
|---|---|---|
| `src/tcn/core/model.py` | Decomposition 𝒯 = (𝒯_E, 𝒯_Q, 𝒯_A) with abstract identities and the assignment functions; derived views (`children`, `path`, …); `positions(𝒯)` | §3.1, Fig. 2a |
| `src/tcn/core/metamodel.py` | `adm(t)`, `mand(t)`, container types ℳ_cont for metamodel v3.1.2 | §3.1 |
| `src/tcn/core/operators.py` | The ten atomic operators, each with `pre`, `apply`, `post` and `mod` | §3.1, Table 1 |
| `src/tcn/core/guarded.py` | Guarded application of an operator and of a chain; completion obligation at the chain boundary | §3.1 |
| `src/tcn/core/transfer.py` | Transfer functions of `Sync`: Identity, ValueMap, Expression (CEL, allowlisted), Instruction | §3.2 |
| `src/tcn/core/addressing.py` | Identification of components by idShort path, qualifier type and attribute key | §3.2, Table 2 |
| `src/tcn/core/matching.py` | Correspondence between a template and a submodel (semanticId, placeholders, list entries) | §3.5 |
| `src/tcn/core/resolution.py` | Rewriting of a template chain into a concrete chain for one submodel instance | §3.5 |
| `src/tcn/core/conformance.py` | Conformance of a submodel to a template: cardinalities, mandatory values, value types | – |
| `src/tcn/dropins.py`, `ressources/DropIns/` | Effective templates: the content of the SMT drop-ins a template uses | – |
| `src/tcn/aas/bridge.py` | AAS JSON (via aas-core3.1) ⇄ formal model | – |
| `src/tcn/aas/tcn_submodel.py` | The TCN Submodel Template and its records | §3.2, Fig. 3 |
| `src/tcn/infra/` | Gateway to the AAS environment, MQTT broker | §4.1, Fig. 4 |
| `src/tcn/roles/` | Template owner, reception, co-evolution | §4.1, Fig. 4 |
| `src/tcn/chainfile.py` | Chain documents (YAML), keyed by the argument names of Table 2 | – |
| `src/tcn/instantiate.py`, `src/tcn/environment.py` | Instances from templates; the AAS of the example device | §5.1 |
| `chains/` | The chains of the validation | §5 |
| `fixtures/` | Submodel instances and the expectations derived by hand | §5.1 |
| `validation/` | The validation cases | §5, Table 4 |
| `ressources/Templates/` | Published SMTs and the TCN SMT (`v0_4` is generated by `uv run tcn smt`) | – |

## Guarantees and how they are checked

`positions(𝒯)` enumerates every position ⟨f, x⟩ of a template with its value. For every operator
application, `validation/properties.py` checks, independently of the operator:

- **accepted** ⇒ the post-condition holds, the changed positions are a subset of `mod`, and the
  result is structurally valid;
- **rejected** ⇒ the template is returned unchanged, no position is written;
- the input is never mutated.

`validation/test_operators.py` exercises one accepted case and one case per rejection code for
each operator.

## Chains

A chain document is authored as an *intent* file and completed by the template owner:

```bash
uv run tcn owner complete chains/technicaldata_1.2_to_2.0.intent.yaml chains/technicaldata_1.2_to_2.0.yaml
```

Every section of a chain states its origin:

| Origin | Meaning |
|---|---|
| `hand` | written by the template owner: relocations (`UpdateParent`), links (`Sync`), renames — the intent of the revision |
| `rule` | a rule the owner declares, expanded in place (`QualifierTypeRenames`, `RemoveSubtree`, `RemoveChildren`, `RenameContainer`) |
| `generated` | mechanical completion of the remaining attribute-level differences |

`uv run tcn owner verify <chain>` checks that the chain transforms v_i into v_i+1 at every position;
only verified chains are published.

| Chain | Items | hand | rule | generated |
|---|---:|---:|---:|---:|
| Technical Data v1.2 → v2.0 | 867 | 56 | 80 | 731 |
| Digital Nameplate v1.0 → v2.0 | 1108 | 65 | – | 1043 |
| Digital Nameplate v2.0 → v3.0 | 821 | 114 | 280 | 427 |
| TCN Submodel Template v0.3 → v0.4 | 926 | 28 | 263 | 635 |

- **Items**: number of atomic operations (items of change) in the completed chain, i.e. in the
  TCN record that is published.
- **hand / rule / generated**: how many of these items come from sections of each origin (see the
  table above). *hand* is the part that states the intent of the revision.

## Resolution

A chain is written against the template, in which each repeatable element has one representative.
Before anything is applied, `resolve` rewrites it for one submodel instance; the rules are stated
in the module documentation of `src/tcn/core/resolution.py`. In short:

- elements are matched by semanticId, placeholders (`arbitrary`) by type (M1, M2);
- an item is expanded once per realisation; unrealised optional branches and placeholders are
  elided, anything else is refused (E1, E2);
- a created element is realised once per realisation of its origin, the common ancestor of the
  content moved or synchronised into it, so that a collection with several items becomes a list
  with one entry per item (C1, C2);
- qualifiers, template example values and the identity of the instance are not propagated (T1–T5);
- containers with instance content are moved by hollow-out, and name collisions are resolved by
  temporary renames (H1, N1).

Every elided, inserted and manual step is reported by `tcn preview` before consent.

## Drop-ins

A published template may leave the content of an element to an SMT drop-in: the element carries
the supplementalSemanticId `https://admin-shell.io/smt-dropin/smt-dropin-use/1/0` and no children.
The Digital Nameplate v3.0 does so for `AddressInformation`; IDTA 02006-3-0 §3.4 states that its
content is the SMC `ContactInformation` of IDTA 02002 Contact Information and that `Street`,
`Zipcode`, `CityTown` and `NationalCode` are mandatory — "only listed in the document, not in the
AASX file".

The demonstrator works on *effective templates*: `src/tcn/dropins.py` inserts the content of every
drop-in found in `ressources/DropIns/catalogue.yaml`. Chains, resolution and the conformance check
use the effective templates, so that the content of a drop-in is neither discarded as unknown nor
missed as a requirement. A drop-in that is not in the catalogue is requested from the asset
maintainer before consent (`DROPIN_UNRESOLVED` in the to-do list): until it is available, the
conformance check cannot judge the content of the element, which is kept and listed as not
described by the template. The template owner derives chains from effective templates as well, so
that a chain retains the content of a drop-in instead of removing it.

## Validation cases

| Case | Method | Test |
|---|---|---|
| V1 Technical Data v1.2 → v2.0 | Analysis | `test_v1_v2_expressiveness.py` |
| V2 Digital Nameplate v1.0 → v2.0 → v3.0 | Analysis | `test_v1_v2_expressiveness.py` |
| V3 Technical Data, end to end | Demonstration | `test_resolution.py` (offline), `test_e2e.py` |
| V4 Digital Nameplate, end to end, same code | Demonstration | `test_resolution.py` (offline), `test_e2e.py` |
| V5 version gap v1.0 → v3.0 via two records | Demonstration | `test_resolution.py` (offline), `test_e2e.py` |
| V6 chain not resolvable against the submodel | Test | `test_resolution.py`, `test_e2e.py` |
| V7 no change before consent | Demonstration | `test_e2e.py` |
| V8 the TCN states the revision of its own template, v0.3 → v0.4 | Analysis, demonstration | `test_v1_v2_expressiveness.py`, `test_resolution.py`, `test_v8_self_application.py` |

- **Method** (paper §5.1): *analysis* examines the operator set against template revisions;
  *demonstration* runs the workflow from the template owner to the asset maintainer; *test*
  examines the behaviour in off-nominal situations.
- **Test**: the files in `validation/` that check the case. `test_resolution.py` runs without
  Docker; `test_e2e.py` runs against the AAS environment and the MQTT broker.

The expectations of V3–V5 (`fixtures/expected/`) were derived by hand from the published change
logs: the instance values to be retained, a control set of elements the revision does not concern,
and the values the asset maintainer has to provide.

### Results

Run of 2026-09-28 against Eclipse BaSyx Go 1.1.0 (PostgreSQL 18) and RabbitMQ 4.3.4: **113 of 113
tests passed**. All cases hold.

**Operators.** Every operator of Table 1 is exercised with one accepted case and one case per
rejection code (43 cases). For every accepted case, the post-condition holds, only positions in
`mod` change and the result is structurally valid; for every rejected case, no position changes.

**Expressiveness (V1, V2).** The chain of each transition is applied to the template v_i and the
result is compared with the template v_i+1. Both are the effective templates, i.e. the published
templates with the content of the drop-ins they use (Digital Nameplate v3.0 and TCN v0.4:
Address Information). Apart from that content, which the published AASX files do not list, they
coincide with the published templates.

| Transition | Items (hand / rule / generated) | Target reproduced | Violations result / published | Differences not stated in the change log |
|---|---|---|---|---|
| Technical Data v1.2 → v2.0 | 867 (56 / 80 / 731) | 545 of 545 facts | 28 / 28 | none |
| Digital Nameplate v1.0 → v2.0 | 1108 (65 / – / 1043) | 811 of 811 facts | 2 / 2 | root idShort `Nameplate` → `DigitalNameplate`; `ManufacturerProductFamily` One → ZeroToOne |
| Digital Nameplate v2.0 → v3.0 | 821 (114 / 280 / 427) | 608 of 608 facts | 6 / 6 | root idShort → `Nameplate`; `OrderCodeOfManufacturer` ZeroToOne → One; both `ArbitraryProperty` OneToMany → ZeroToMany |
| V8: TCN Submodel Template v0.3 → v0.4 | 926 (28 / 263 / 635) | 616 of 616 facts | 0 / 0 | none |

- **Items (hand / rule / generated)**: size of the chain and the origin of its items, as in
  [Chains](#chains).
- **Target reproduced**: the templates are compared as sets of *facts*, independent of the order
  of siblings: one fact per element (path, type, idShort), per qualifier (element path, qualifier
  type) and per attribute (owner, name, value). "545 of 545" means that the result contains every
  fact of v_i+1; in addition, it contains no fact that v_i+1 lacks.
- **Violations result / published**: number of metamodel constraint violations aas-core reports for
  the result and for the published v_i+1. The published templates are themselves not free of
  violations; equal numbers (and equal kinds) mean that the chain introduces none.
- **Differences not stated in the change log**: values of constraints (cardinalities) and
  idShorts that change between the published versions although the change log does not mention
  them. They surface as generated items that overwrite an existing value.

In all four chains, every relocation (`UpdateParent`) and every value link (`Sync`) is stated by
the template owner, none is generated.

**Application to submodels (V3–V5, V8).** The chain is resolved against a submodel instance
(`fixtures/`) and applied to it. The instances contain several realisations of repeatable elements
(two product images, two classifications, two markings, …) and a local extension of the asset
maintainer that no template describes.

| Case | Operations on the submodel | Elided / inserted | Retained values | Values removed | Control set unchanged | Baseline unchanged | Conforms to v_i+1 | To do for the asset maintainer |
|---|---:|---:|---|---|---|---|---|---|
| V3 Technical Data v1.2 → v2.0 | 241 | 703 / 18 | 16 of 16 | none | 5 of 5 | yes | no | provide `ProductClassCodedName` in both classifications (mandatory, new in v2.0) |
| V4 Digital Nameplate v2.0 → v3.0 | 277 | 614 / 14 | 28 of 28, incl. 6 multi-language → string conversions (CEL) and the contact data in the drop-in `AddressInformation` | none | 4 of 4 | yes | yes | nothing |
| V5 Digital Nameplate v1.0 → v3.0, two records | 298 | 1678 / 6 | 12 of 12, incl. the address, via `ContactInformation` into `AddressInformation` | `VATNumber` (not continued in v2.0) | 1 of 1 | yes | no | provide `URIOfTheProduct` (mandatory since v2.0) and `OrderCodeOfManufacturer` (mandatory since v3.0) |
| V8 TCN submodel v0.3 with one record → v0.4 | 282 | 714 / 0 | 13 of 13 | the two values of `ReasonsOfChange` (not in v0.4) | 1 of 1 | yes | yes (structure) | rewrite 7 values from the v0.3 encoding, as instructed (see below) |

- **Operations on the submodel**: number of atomic operations of the concrete chain that resolution
  derives for this instance and that is applied to it. It differs from the number of items of the
  template chain: an item is expanded once per realisation, and items are elided or inserted.
- **Elided**: items of the template chain that are not applied to this instance, each with its
  reason, e.g. operations on qualifiers (template constructs), template example values (instance
  data is not overwritten), and elements of optional branches the instance does not realise.
  Operations on qualifiers make up half to three quarters of the elisions (V3 61 %, V4 76 %,
  V5 51 %, V8 59 %); most of the rest concern elements of optional branches.
- **Inserted**: operations that resolution adds although the chain does not state them: temporary
  renames while elements are parked (rule N1) and the rebuilding of containers that have instance
  content (rule H1).
- **Retained values**: instance values that, according to the expectation derived by hand
  (`fixtures/expected/`), must be found at their path after the change, and were found there.
- **Values removed**: values of the submodel that the change removes without carrying them over,
  because the new template has no place for them. They are reported before consent, as a warning,
  with path and value. A test checks for every case that no value is lost silently: each value of
  the submodel is afterwards still at its element, converted automatically, subject to a reported
  instruction, or reported as removed.
- **Control set unchanged**: elements the revision does not concern (local extensions, properties
  defined by the instance) whose attributes are identical after the change; their path may change
  where a container they belong to is relocated.
- **Baseline unchanged**: the previous revision of the submodel is identical after the application.
- **Conforms to v_i+1**: the result of the application, checked against the new template
  (`src/tcn/core/conformance.py`): every mandatory element present and with a value, no element
  realised more often than its cardinality allows, value types as in the template. Elements the
  template does not describe (local extensions) do not affect conformance. The check sees structure,
  not the meaning of values: in V8 it cannot tell that a path is still in the v0.3 encoding.
- **To do for the asset maintainer**: what remains after the application: the violations of the
  new template, and the transformations stated as instructions. The result conforms, and nothing is
  to do, once these steps are carried out.

Elided, inserted, converted and removed values, conformance and the to-do list are all reported by
`tcn preview` before consent. Every fixture conforms to v_i before the application.

V5, out of order: the v2.0 → v3.0 record applied first is refused with `VERSION_MISMATCH`; the
complete enumeration of shells and submodels is identical before and after. In order, each record
applies, and the submodel declares v2.0 and then v3.0 as its template.

**Self-application (V8).** The TCN states the revision of its own template: MCN naming becomes
the naming of the paper, `syncMapping` (the name of a transformation) becomes the collection
`TransferFunction`, paths lose the prefix `<submodelId>::`, and attribute values become
JSON-encoded. The chain reproduces v0.4 at every position. Applied to a TCN submodel v0.3 holding a
record of four items, it yields a TCN submodel v0.4 without metamodel violations: the items keep
their values under the new names, and `syncMapping: identity` becomes `TransferFunction.Kind:
Identity` (ValueMap). After the asset maintainer has carried out the seven reported manual steps,
the migrated record states exactly the chain the v0.3 record stated (`test_v8_self_application.py`).

Two findings. (i) The paths and literal values of records cannot be rewritten automatically (yet): core
CEL has no string functions (`split`, `substring`, `replace`), so these transformations are
instructions. (ii) Renaming a container that has children is only possible by rebuilding it
(Hollow-Out), since `UpdateIdShort` requires an element without children; two renamed containers
that carry the whole tree account for 263 of the 926 items. The rule `RenameContainer` states this
intent once and expands it into atomic operations.

**Guarded application (V6, V7).** "Complete enumeration of the environment" compares all shells
and submodels of the AAS environment, before and after.

| Case | Result |
|---|---|
| V6 submodel lacks a mandatory element (`GeneralInformation.ManufacturerName`) | refused before application with `SEMANTIC_MATCH_NONE`; complete enumeration of the environment identical before and after; reason set aside in `quarantine/`; record remains waiting |
| V7 four interactions between reception and consent: listing records, preview, reading the submodel, applying without consent | shell and submodel unchanged after each; applying without consent is rejected |

## Security of transfer functions

An `Expression` is evaluated only if its language is on the receiver's allowlist — currently
[CEL](https://github.com/google/cel-spec), evaluated by the interpreting runner of `cel-python`. CEL
terminates on every input and has no side effects; the expression sees nothing but the source
values. A payload therefore never becomes code. Expressions in other languages, and instructions,
are handed to the asset maintainer and never executed.

## Open-source software and content used

The demonstrator builds on the following projects. Their licenses are those stated by the projects
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
