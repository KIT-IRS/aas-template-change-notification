"""Command-line interface of both roles.

Template owner
    tcn owner complete <intent.yaml> <out.yaml>   expand rules and complete the chain
    tcn owner verify   <chain.yaml>               check that the chain yields v_i+1
    tcn owner publish  <chain.yaml>               verify and publish the chain as TCN record
Asset maintainer
    tcn seed | reset                              set up / remove the AAS of the example device
    tcn receive [--seconds N]                     file received records into the TCN submodel
    tcn list                                      filed records and whether they are applicable
    tcn preview <notificationId>                  effect of a record; nothing is written
    tcn apply   <notificationId> --consent        apply a record
Other
    tcn smt <out.json>                            write the TCN Submodel Template
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tcn import chainfile, environment
from tcn.aas import tcn_submodel
from tcn.core.guarded import ACC
from tcn.infra.gateway import Gateway
from tcn.roles import coevolution, reception, template_owner


def _owner_complete(args) -> int:
    chain = template_owner.complete(chainfile.load(args.intent))
    chainfile.dump(chain, args.out)
    for s in chain.sections:
        print(f"{len(s.items):5}  {s.origin:9}  {s.title}")
    print(f"{len(chain.items):5}  items written to {args.out}")
    return _owner_verify(argparse.Namespace(chain=args.out))


def _owner_verify(args) -> int:
    v = template_owner.verify(chainfile.load(args.chain))
    print(f"chain {v.result.status}" + (f": {v.result.reason}" if v.result.reason else ""))
    print(f"v_i+1 reproduced: {v.ok}  (missing {len(v.missing)}, surplus {len(v.surplus)})")
    for fact in sorted(v.missing):
        print("  missing ", fact)
    for fact in sorted(v.surplus):
        print("  surplus ", fact)
    return 0 if v.ok else 1


def _owner_publish(args) -> int:
    print(f"published {template_owner.publish(chainfile.load(args.chain))}")
    return 0


def _seed(args) -> int:
    environment.seed(Gateway())
    print(f"seeded {environment.AAS_ID}")
    return 0


def _reset(args) -> int:
    environment.reset(Gateway())
    print(f"removed everything below {environment.NAMESPACE}")
    return 0


def _receive(args) -> int:
    for line in reception.run(Gateway(), environment.TCN_ID, list(environment.FIXTURES), args.seconds):
        print(line)
    return 0


def _list(args) -> int:
    for e in coevolution.records(Gateway(), environment.TCN_ID):
        h = e.chain.header
        state = "applicable" if e.applicable else "not applicable"
        print(f"{h['NotificationId']}  {h['PreVersion']} -> {h['PostVersion']}  "
              f"{len(e.chain.items)} items  {state}  ({e.submodel_id})")
    return 0


def _print_report(r: coevolution.Report, verbose: bool = False) -> None:
    if r.resolution:
        for n in r.resolution.notes:
            if n.kind in ("inserted", "refused") or (verbose and n.kind != "expanded"):
                print(f"  item {n.index:4}  {n.kind:8}  {n.detail}")
        print(f"{len(r.resolution.items)} operations for the submodel; " + ", ".join(
            f"{k} {r.resolution.count(k)}" for k in ("elided", "inserted", "manual"))
            + ("" if verbose else "  (--verbose lists the elided items)"))
    if r.conformance is not None:
        conforms = not any(f.kind in coevolution.VIOLATIONS for f in r.conformance)
        print(f"\nResult conforms to the new template: {'yes' if conforms else 'no'}")
        for f in r.conformance:
            if f.kind == "NOT_IN_TEMPLATE":
                print(f"  not described by the template (kept): {f.path}")
        converted = [n for n in r.resolution.notes if n.kind == "transferred"] if r.resolution else []
        if converted:
            print("\nValues converted automatically:")
            for n in converted:
                print(f"  - {n.path}: {n.detail}")
        if r.removed:
            print(f"\nWARNING: this change removes {len(r.removed)} value(s) of the submodel without carrying "
                  f"them over.\nBy consenting, you accept their removal; keep them elsewhere if they are still needed:")
            for path, value in r.removed:
                print(f"  - {path} = {value}")
        else:
            print("\nNo value of the submodel is removed.")
        print("To do for the asset maintainer:" if r.todo else "Nothing to do for the asset maintainer.")
        for line in r.todo:
            print(f"  - {line}")
    print(f"\n{r.status}" + (f": {r.reason}" if r.reason else "")
          + (f"  -> new revision {r.new_revision}" if r.new_revision else ""))


def _preview(args) -> int:
    r = coevolution.preview(Gateway(), environment.TCN_ID, args.notification_id)
    _print_report(r, args.verbose)
    return 0 if r.status == ACC else 1


def _apply(args) -> int:
    if not args.consent:
        print("not applied: a TCN is applied only upon explicit consent (--consent)")
        return 2
    r = coevolution.apply(Gateway(), environment.TCN_ID, environment.AAS_ID, args.notification_id, args.consent)
    _print_report(r, args.verbose)
    return 0 if r.status == ACC else 1


def _smt(args) -> int:
    Path(args.out).write_text(json.dumps(tcn_submodel.template(), indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"TCN Submodel Template written to {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tcn")
    roles = parser.add_subparsers(dest="role", required=True)

    owner = roles.add_parser("owner", help="template owner").add_subparsers(dest="cmd", required=True)
    p = owner.add_parser("complete")
    p.add_argument("intent")
    p.add_argument("out")
    p.set_defaults(func=_owner_complete)
    p = owner.add_parser("verify")
    p.add_argument("chain")
    p.set_defaults(func=_owner_verify)

    p = owner.add_parser("publish")
    p.add_argument("chain")
    p.set_defaults(func=_owner_publish)

    for name, func in [("seed", _seed), ("reset", _reset), ("list", _list)]:
        roles.add_parser(name).set_defaults(func=func)
    p = roles.add_parser("receive")
    p.add_argument("--seconds", type=float, default=30)
    p.set_defaults(func=_receive)
    p = roles.add_parser("preview")
    p.add_argument("notification_id")
    p.add_argument("--verbose", action="store_true", help="list every elided item")
    p.set_defaults(func=_preview)
    p = roles.add_parser("apply")
    p.add_argument("notification_id")
    p.add_argument("--verbose", action="store_true", help="list every elided item")
    p.add_argument("--consent", action="store_true", help="explicit consent of the asset maintainer")
    p.set_defaults(func=_apply)

    p = roles.add_parser("smt", help="write the TCN Submodel Template")
    p.add_argument("out")
    p.set_defaults(func=_smt)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
