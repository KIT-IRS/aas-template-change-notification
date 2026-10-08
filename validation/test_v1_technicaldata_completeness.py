"""V1: Technical Data v1.2 -> v2.0  (paper §5.2, Table 4, Table 5).

Requirements R1, R2. Method: analysis.
Pass criterion: the chain, applied to v1.2, reproduces every fact of v2.0 and no further fact and
introduces no metamodel violation. Differences between the templates that the change log does not
state are enumerated. The checks are described in validation/analysis.py.

The opposite case, a change the change log lists but the template does not carry out, cannot show in
a chain and is not checked: Technical Data v2.0 lists a rename of ClassificationSystemVersion, which
keeps its idShort in the published template (paper §3.1, §5.2).
"""

from validation import analysis

CHAIN = "chains/technicaldata_1.2_to_2.0.yaml"
UNDOCUMENTED = [
    ("G1", ("GeneralInformation.ManufacturerLogo", "idShort", "CompanyLogo")),
    ("G8", None),  # qualifier type Cardinality -> SMT/Cardinality, listed only as part of the schema update
]
GENERATED_OVERWRITES = set()


def test_chain_reproduces_target_template():
    analysis.check_chain_reproduces_target_template(CHAIN)


def test_result_is_metamodel_conformant_as_published():
    analysis.check_result_is_metamodel_conformant_as_published(CHAIN)


def test_relocations_and_links_are_stated_by_hand():
    analysis.check_relocations_and_links_are_stated_by_hand(CHAIN)


def test_undocumented_differences_are_enumerated():
    analysis.check_undocumented_differences_are_enumerated(CHAIN, UNDOCUMENTED, GENERATED_OVERWRITES)
