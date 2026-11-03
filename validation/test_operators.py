"""Every operator of Table 1: one accepted case and one rejected case per rejection code.

Each case is checked by properties.check_guarded, i.e. post-condition, modified set, structural
validity (ACC) and an unchanged template (REJ).
"""

import pytest

from tcn.aas import bridge
from tcn.core import operators as op
from tcn.core.addressing import attribute as A
from tcn.core.addressing import element as E
from tcn.core.addressing import qualifier as Q
from tcn.core.guarded import ACC
from tcn.core.model import LAMBDA
from tcn.core.transfer import CEL, Expression, Identity, Instruction, ValueMap

from validation.properties import check_guarded

CARD = "SMT/Cardinality"

FIXTURE = {
    "modelType": "Submodel", "id": "urn:test:sm", "idShort": "Test", "kind": "Template",
    "submodelElements": [
        {"modelType": "SubmodelElementCollection", "idShort": "C",
         "qualifiers": [{"type": CARD, "valueType": "xs:string", "value": "One"}],
         "value": [{"modelType": "Property", "idShort": "P", "valueType": "xs:string", "value": "1"}]},
        {"modelType": "SubmodelElementList", "idShort": "L",
         "typeValueListElement": "SubmodelElementCollection",
         "value": [{"modelType": "SubmodelElementCollection"}]},
        {"modelType": "Property", "idShort": "X", "valueType": "xs:double", "value": "2.5"},
        {"modelType": "Range", "idShort": "R", "valueType": "xs:double"},
    ],
}

CASES = [
    # CreateSME
    ("CreateSME", lambda T: op.CreateSME(E(T, "C"), "Property", "New"), ACC),
    ("CreateSME list entry", lambda T: op.CreateSME(E(T, "L"), "SubmodelElementCollection", None), ACC),
    ("CreateSME", lambda T: op.CreateSME(E(T, "C"), "Property", "P"), "IDSHORT_UNIQUE"),
    ("CreateSME", lambda T: op.CreateSME(E(T, "X"), "Property", "New"), "PARENT_IS_CONTAINER"),
    ("CreateSME", lambda T: op.CreateSME(999, "Property", "New"), "PARENT_EXISTS"),
    ("CreateSME", lambda T: op.CreateSME(E(T, "C"), "Submodel", "New"), "TYPE_ADMISSIBLE"),
    ("CreateSME", lambda T: op.CreateSME(E(T, "C"), "Property", None), "IDSHORT_REQUIRED"),
    # CreateQual
    ("CreateQual", lambda T: op.CreateQual(E(T, "C.P"), CARD), ACC),
    ("CreateQual", lambda T: op.CreateQual(E(T, "C"), CARD), "QUAL_EXISTS"),
    ("CreateQual", lambda T: op.CreateQual(999, CARD), "TARGET_EXISTS"),
    # CreateAttr
    ("CreateAttr", lambda T: op.CreateAttr(E(T, "C.P"), "valueId"), ACC),
    ("CreateAttr on qualifier", lambda T: op.CreateAttr(Q(T, "C", CARD), "valueId"), ACC),
    ("CreateAttr", lambda T: op.CreateAttr(E(T, "C.P"), "value"), "ATTR_EXISTS"),
    ("CreateAttr", lambda T: op.CreateAttr(E(T, "C.P"), "min"), "ATTR_APPLICABLE"),
    ("CreateAttr", lambda T: op.CreateAttr(Q(T, "C", CARD), "category"), "ATTR_APPLICABLE"),
    ("CreateAttr", lambda T: op.CreateAttr(999, "value"), "TARGET_EXISTS"),
    # UpdateIdShort
    ("UpdateIdShort", lambda T: op.UpdateIdShort(E(T, "C.P"), "P2"), ACC),
    ("UpdateIdShort root", lambda T: op.UpdateIdShort(T.root, "Renamed"), ACC),
    ("UpdateIdShort", lambda T: op.UpdateIdShort(E(T, "C"), "C2"), "NO_CHILDREN"),
    ("UpdateIdShort", lambda T: op.UpdateIdShort(E(T, "X"), "R"), "IDSHORT_UNIQUE"),
    # UpdateParent
    ("UpdateParent", lambda T: op.UpdateParent(E(T, "X"), E(T, "C")), ACC),
    ("UpdateParent into list entry", lambda T: op.UpdateParent(E(T, "C.P"), E(T, "L[0]")), ACC),
    ("UpdateParent", lambda T: op.UpdateParent(E(T, "C"), E(T, "L[0]")), "NO_CHILDREN"),
    ("UpdateParent", lambda T: op.UpdateParent(E(T, "X"), E(T, "R")), "PARENT_IS_CONTAINER"),
    ("UpdateParent", lambda T: op.UpdateParent(E(T, "X"), 999), "PARENT_EXISTS"),
    ("UpdateParent", lambda T: op.UpdateParent(T.root, E(T, "C")), "TARGET_EXISTS"),
    ("UpdateParent", lambda T: op.UpdateParent(E(T, "L[0]"), E(T, "L[0]")), "CYCLIC_PARENT"),
    # UpdateAttr
    ("UpdateAttr", lambda T: op.UpdateAttr(A(T, "X", None, "value"), "3.0"), ACC),
    ("UpdateAttr", lambda T: op.UpdateAttr(999, "3.0"), "ATTR_ABSENT"),
    # RemoveSME
    ("RemoveSME", lambda T: op.RemoveSME(E(T, "X")), ACC),
    ("RemoveSME", lambda T: op.RemoveSME(E(T, "L")), "NO_CHILDREN"),
    ("RemoveSME", lambda T: op.RemoveSME(T.root), "TARGET_EXISTS"),
    # RemoveQual
    ("RemoveQual", lambda T: op.RemoveQual(Q(T, "C", CARD)), ACC),
    ("RemoveQual", lambda T: op.RemoveQual(999), "QUAL_ABSENT"),
    # RemoveAttr
    ("RemoveAttr", lambda T: op.RemoveAttr(A(T, "X", None, "value")), ACC),
    ("RemoveAttr", lambda T: op.RemoveAttr(999), "ATTR_ABSENT"),
    # Sync
    ("Sync Identity", lambda T: op.Sync([A(T, "X", None, "value")], [A(T, "C.P", None, "value")],
                                        Identity()), ACC),
    ("Sync ValueMap", lambda T: op.Sync([A(T, "C", CARD, "value")], [A(T, "C.P", None, "value")],
                                        ValueMap({"One": "ZeroToOne"})), ACC),
    ("Sync Instruction", lambda T: op.Sync([A(T, "X", None, "value")], [A(T, "C.P", None, "value")],
                                           Instruction({"en": "convert by hand"})), ACC),
    ("Sync", lambda T: op.Sync([A(T, "X", None, "value")], [A(T, "C.P", None, "value")],
                               ValueMap({"One": "ZeroToOne"})), "TRANSFER_UNDEFINED"),
    ("Sync nested error", lambda T: op.Sync([A(T, "X", None, "value")], [A(T, "C.P", None, "value")],
                                            Expression(CEL, "[[src[0] + 1]]")), "TRANSFER_UNDEFINED"),
    ("Sync", lambda T: op.Sync([A(T, "X", None, "value")], [A(T, "C.P", None, "value")],
                               Expression(CEL, "[[src[0]]]")), "TRANSFER_INADMISSIBLE"),
    ("Sync", lambda T: op.Sync([A(T, "X", None, "value")], [], Identity()), "TARGET_EMPTY"),
    ("Sync", lambda T: op.Sync([A(T, "X", None, "value")] * 2, [A(T, "C.P", None, "value")],
                               Identity()), "ARITY_MISMATCH"),
    ("Sync", lambda T: op.Sync([999], [A(T, "C.P", None, "value")], Identity()), "ATTR_ABSENT"),
]


@pytest.mark.parametrize("name, make, expected", CASES, ids=[f"{c[0]}-{c[2]}" for c in CASES])
def test_operator(name, make, expected):
    T = bridge.from_jsonable(FIXTURE)
    _, outcome = check_guarded(make(T), T)
    assert (outcome.reason or ACC) == expected


def test_create_sme_creates_mandatory_slots():
    T = bridge.from_jsonable(FIXTURE)
    T2, _ = check_guarded(op.CreateSME(E(T, "C"), "Property", "New"), T)
    new = E(T2, "C.New")
    assert [(T2.A[a].name, T2.A[a].value) for a in T2.attributes(new)] == [("valueType", LAMBDA)]
