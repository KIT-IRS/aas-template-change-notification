"""Metamodel parameters adm(t), mand(t) and M_cont for IDTA-01001 v3.1.2  (paper §3.2).

They depend on the component type only, are identical for all templates and change only with the
metamodel. Attribute names are the keys of the AAS JSON serialisation. Whether an attribute value
has an admissible form is decided by aas-core (admissible).
"""

from typing import Any

from aas_core3_1 import jsonization

METAMODEL_VERSION = "3.1.2"

# Admissible for every Referable element by inheritance; never mandatory.
COMMON = {"semanticId", "supplementalSemanticIds", "displayName", "description", "category",
          "embeddedDataSpecifications"}

# type t -> (adm(t) without COMMON, mand(t))
_TABLE: dict[str, tuple[set[str], set[str]]] = {
    "Submodel": ({"id", "administration", "kind"}, {"id"}),
    "Property": ({"valueType", "value", "valueId"}, {"valueType"}),
    "Range": ({"valueType", "min", "max"}, {"valueType"}),
    "MultiLanguageProperty": ({"value", "valueId"}, set()),
    "File": ({"value", "contentType"}, set()),
    "Blob": ({"value", "contentType"}, set()),
    "ReferenceElement": ({"value"}, set()),
    "RelationshipElement": ({"first", "second"}, set()),
    "AnnotatedRelationshipElement": ({"first", "second"}, set()),
    "Capability": (set(), set()),
    "BasicEventElement": ({"observed", "direction", "state", "messageTopic", "messageBroker",
                           "lastUpdate", "minInterval", "maxInterval"},
                          {"observed", "direction", "state"}),
    "SubmodelElementCollection": (set(), set()),
    "SubmodelElementList": ({"typeValueListElement", "valueTypeListElement",
                             "semanticIdListElement", "orderRelevant"},
                            {"typeValueListElement"}),
    "Entity": ({"entityType", "globalAssetId", "specificAssetIds"}, set()),
}

# A Qualifier is neither Referable nor Qualifiable: it does not inherit COMMON.
_QUALIFIER = ({"kind", "valueType", "value", "valueId", "semanticId", "supplementalSemanticIds"},
              {"valueType"})

# Container types and the JSON key under which each holds its children.
CONTAINMENT_KEY = {
    "Submodel": "submodelElements",
    "SubmodelElementCollection": "value",
    "SubmodelElementList": "value",
    "Entity": "statements",
    "AnnotatedRelationshipElement": "annotations",
}
M_CONT = set(CONTAINMENT_KEY)

ELEMENT_TYPES = set(_TABLE) - {"Submodel"}


def adm(t: str) -> set[str]:
    if t == "Qualifier":
        return _QUALIFIER[0]
    return _TABLE[t][0] | COMMON


def mand(t: str) -> set[str]:
    return _QUALIFIER[1] if t == "Qualifier" else _TABLE[t][1]


def admissible(t: str, attributes: dict[str, Any], name: str, value: Any) -> bool:
    """Whether `value` is admissible for the attribute `name` of a component of type t whose other
    populated attributes are `attributes` (for a qualifier including its "type"): aas-core can
    deserialise the component with it. Only the form is decided, not the constraints of the
    metamodel. If the component cannot be deserialised even without the attribute (e.g. a
    mandatory attribute is still unpopulated), the value is not judged and taken as admissible."""

    def parses(d: dict[str, Any]) -> bool:
        try:
            if t == "Qualifier":
                jsonization.qualifier_from_jsonable(d)
            elif t == "Submodel":
                jsonization.submodel_from_jsonable({"modelType": t} | d)
            else:
                jsonization.submodel_element_from_jsonable({"modelType": t} | d)
            return True
        except jsonization.DeserializationException:
            return False

    others = {k: v for k, v in attributes.items() if k != name}
    return not parses(others) or parses(others | {name: value})
