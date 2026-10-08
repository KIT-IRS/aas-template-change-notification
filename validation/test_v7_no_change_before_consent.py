"""V7: publication without consent  (paper §5.4, Table 4).

Requirement R4. Method: demonstration.
Pass criterion: the submodel remains unchanged between the reception of a record and the consent of
the asset maintainer, while unrelated interactions continue. Since the absence of a change over an
arbitrary period does not establish this property, the test interleaves interactions of the asset
maintainer and requires shell and submodel to be unchanged after each of them.
"""

import pytest

from tcn import environment
from tcn.roles import coevolution
from validation.endtoend import deliver


@pytest.mark.infra
def test_no_change_before_consent(gw):
    nid = deliver(gw, "chains/technicaldata_1.2_to_2.0.yaml")
    sm_id = next(e.submodel_id for e in coevolution.records(gw, environment.TCN_ID)
                 if e.chain.header["NotificationId"] == nid)
    state = (gw.get_shell(environment.AAS_ID), gw.get_submodel(sm_id))
    interactions = [
        lambda: coevolution.records(gw, environment.TCN_ID),
        lambda: coevolution.preview(gw, environment.TCN_ID, nid),
        lambda: gw.get_submodel(sm_id),
        lambda: pytest.raises(PermissionError, coevolution.apply, gw, environment.TCN_ID,
                              environment.AAS_ID, nid, consent=False),
    ]
    for interact in interactions:
        interact()
        assert (gw.get_shell(environment.AAS_ID), gw.get_submodel(sm_id)) == state
