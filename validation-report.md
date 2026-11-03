# Validation report

- run: 2026-10-15T15:57:34
- revision: TCN-v0.4-8-g00cdd89
- python: 3.13.14
- selection: all tests

## Validation cases

| case | subject | requirements | method | checks | result |
|---|---|---|---|---:|---|
| V1 | Technical Data v1.2 -> v2.0 | R1, R2 | analysis | 4/4 | passed |
| V2 | Digital Nameplate ZVEI 1.0 -> IDTA 2.0 -> IDTA 3.0 | R1, R2 | analysis | 8/8 | passed |
| V3 | Technical Data v1.2 -> v2.0, end to end | R2, R4 | demonstration | 7/7 | passed |
| V4 | Digital Nameplate IDTA 2.0 -> IDTA 3.0, end to end | R2, R4 | demonstration | 6/6 | passed |
| V5 | Digital Nameplate ZVEI 1.0 -> IDTA 3.0 via two records | R3, R4 | demonstration | 6/6 | passed |
| V6 | chain that cannot be resolved against the local submodel | R4 | test | 2/2 | passed |
| V7 | publication without consent | R4 | demonstration | 1/1 | passed |
| V8 | TCN Submodel Template v0.3 -> v0.4 | R1, R2, R3 | analysis, demonstration | 10/10 | passed |

## Supporting tests

| tests | subject | checks | result |
|---|---|---:|---|
| `test_bridge.py` | The decomposition is lossless: SMT -> T -> SMT reproduces every template unchanged | 8/8 | passed |
| `test_conformance.py` | The conformance check of a submodel against its Submodel Template, one case per finding | 7/7 | passed |
| `test_operators.py` | Every operator of Table 1: one accepted case and one rejected case per rejection code | 44/44 | passed |
| `test_tcn_submodel.py` | The TCN submodel (paper §3.5): template, and records that carry a chain without loss | 5/5 | passed |
| `test_transfer.py` | Transfer functions of Sync (paper §3.5, §4.2): execution of expressions without executing code | 5/5 | passed |

## V1: Technical Data v1.2 -> v2.0 — passed

Requirements R1, R2. Method: analysis.

Pass criterion: the chain, applied to v1.2, reproduces every fact of v2.0 and no further fact and introduces no metamodel violation. Differences between the templates that the change log does not state are enumerated. The checks are described in validation/analysis.py.

| check | parameter | result | time |
|---|---|---|---:|
| chain reproduces target template |  | passed | 0.94 s |
| result is metamodel conformant as published |  | passed | 0.86 s |
| relocations and links are stated by hand |  | passed | 0.35 s |
| undocumented differences are enumerated |  | passed | 0.87 s |

## V2: Digital Nameplate ZVEI 1.0 -> IDTA 2.0 -> IDTA 3.0 — passed

Requirements R1, R2. Method: analysis.

Pass criterion: as V1, for both transitions. The checks are described in validation/analysis.py. The transition ZVEI 1.0 -> IDTA 2.0 has no published change log, so no undocumented differences are listed for it.

| check | parameter | result | time |
|---|---|---|---:|
| chain reproduces target template | 1.0_to_2.0 | passed | 1.86 s |
| chain reproduces target template | 2.0_to_3.0 | passed | 3.66 s |
| result is metamodel conformant as published | 1.0_to_2.0 | passed | 2.39 s |
| result is metamodel conformant as published | 2.0_to_3.0 | passed | 1.40 s |
| relocations and links are stated by hand | 1.0_to_2.0 | passed | 0.50 s |
| relocations and links are stated by hand | 2.0_to_3.0 | passed | 0.40 s |
| undocumented differences are enumerated | 1.0_to_2.0 | passed | 1.90 s |
| undocumented differences are enumerated | 2.0_to_3.0 | passed | 1.37 s |

## V3: Technical Data v1.2 -> v2.0, end to end — passed

Requirements R2, R4. Method: demonstration.

Pass criterion: instance values designated for retention keep their values, the control set remains unchanged, and every deviation of the result from v2.0 and every removed value is reported before consent. The expectations are in fixtures/expected/technicaldata_1.2_to_2.0.yaml.

| check | parameter | result | time |
|---|---|---|---:|
| chain applies and retains instance data |  | passed | 2.39 s |
| manual steps are reported |  | passed | 4.68 s |
| result is serialisable without new violations |  | passed | 4.50 s |
| conformance to the new template |  | passed | 2.22 s |
| no value is lost silently |  | passed | 1.49 s |
| baseline is not changed |  | passed | 3.05 s |
| end to end |  | passed | 19.06 s |

Application to the instance (`fixtures/expected/technicaldata_1.2_to_2.0.yaml`):

Notes: manual 1, expanded 19, inserted 18, elided 703

| | expectation | expected | observed |
|---|---|---|---|
| ✓ | retained: `GeneralInformation.ManufacturerName` | Example Manufacturer GmbH | Example Manufacturer GmbH |
| ✓ | retained: `GeneralInformation.ManufacturerArticleNumber` | EX-100-200 | EX-100-200 |
| ✓ | retained: `GeneralInformation.ManufacturerOrderCode` | EX100200 | EX100200 |
| ✓ | retained: `GeneralInformation.CompanyLogo` | /aasx/files/logo.png | /aasx/files/logo.png |
| ✓ | retained: `GeneralInformation.ProductImages[0].ImageFile` | /aasx/files/front.jpg | /aasx/files/front.jpg |
| ✓ | retained: `GeneralInformation.ProductImages[1].ImageFile` | /aasx/files/side.jpg | /aasx/files/side.jpg |
| ✓ | retained: `ProductClassifications[0].ClassificationSystem` | ECLASS | ECLASS |
| ✓ | retained: `ProductClassifications[0].ClassificationSystemVersion` | 13.0 | 13.0 |
| ✓ | retained: `ProductClassifications[0].ProductClassId` | 27-24-22-01 | 27-24-22-01 |
| ✓ | retained: `ProductClassifications[1].ClassificationSystem` | UNSPSC | UNSPSC |
| ✓ | retained: `ProductClassifications[1].ProductClassId` | 32151705 | 32151705 |
| ✓ | retained: `TechnicalPropertyAreas[0].Width` | 62.4 | 62.4 |
| ✓ | retained: `TechnicalPropertyAreas[0].Weight` | 0.21 | 0.21 |
| ✓ | retained: `TechnicalPropertyAreas[0].MainSection01.SubSection01.RatedVoltage` | 24 | 24 |
| ✓ | retained: `FurtherInformation.ValidDate` | 2025-06-30 | 2025-06-30 |
| ✓ | retained: `GeneralInformation.InternalInventoryNumber` | INV-2024-0815 | INV-2024-0815 |
| ✓ | control: `GeneralInformation.InternalInventoryNumber → GeneralInformation.InternalInventoryNumber` | unchanged | unchanged |
| ✓ | control: `TechnicalProperties.Width → TechnicalPropertyAreas[0].Width` | unchanged | unchanged |
| ✓ | control: `TechnicalProperties.Weight → TechnicalPropertyAreas[0].Weight` | unchanged | unchanged |
| ✓ | control: `TechnicalProperties.HousingColour → TechnicalPropertyAreas[0].HousingColour` | unchanged | unchanged |
| ✓ | control: `TechnicalProperties.MainSection01.SubSection01.RatedVoltage → TechnicalPropertyAreas[0].MainSection01.SubSection01.RatedVoltage` | unchanged | unchanged |
| ✓ | manual: `ProductClassifications[0].ProductClassCodedName` | 1 | 1 |
| ✓ | violation: `('VALUE_MISSING', 'ProductClassifications[0].ProductClassCodedName')` | 1 | 1 |
| ✓ | violation: `('VALUE_MISSING', 'ProductClassifications[1].ProductClassCodedName')` | 1 | 1 |

## V4: Digital Nameplate IDTA 2.0 -> IDTA 3.0, end to end — passed

Requirements R2, R4. Method: demonstration.

Pass criterion: as V3, without a change to the implementation compared to V3. The tests are those of V3; only the expectations differ (fixtures/expected/nameplate_2.0_to_3.0.yaml).

| check | parameter | result | time |
|---|---|---|---:|
| chain applies and retains instance data |  | passed | 2.89 s |
| manual steps are reported |  | passed | 2.63 s |
| result is serialisable without new violations |  | passed | 2.40 s |
| conformance to the new template |  | passed | 2.96 s |
| no value is lost silently |  | passed | 2.54 s |
| end to end |  | passed | 15.71 s |

Application to the instance (`fixtures/expected/nameplate_2.0_to_3.0.yaml`):

Notes: transferred 6, expanded 58, inserted 14, elided 614

| | expectation | expected | observed |
|---|---|---|---|
| ✓ | retained: `URIOfTheProduct` | https://example.com/products/EX-100-200/SN0042 | https://example.com/products/EX-100-200/SN0042 |
| ✓ | retained: `SerialNumber` | SN0042 | SN0042 |
| ✓ | retained: `YearOfConstruction` | 2024 | 2024 |
| ✓ | retained: `DateOfManufacture` | 2024-03-12 | 2024-03-12 |
| ✓ | retained: `CountryOfOrigin` | DE | DE |
| ✓ | retained: `Markings[0].MarkingName` | CE | CE |
| ✓ | retained: `Markings[0].IssueDate` | 2024-01-10 | 2024-01-10 |
| ✓ | retained: `Markings[0].MarkingFile` | /aasx/files/ce.pdf | /aasx/files/ce.pdf |
| ✓ | retained: `Markings[1].MarkingName` | UKCA | UKCA |
| ✓ | retained: `Markings[1].IssueDate` | 2024-02-01 | 2024-02-01 |
| ✓ | retained: `Markings[1].MarkingFile` | /aasx/files/ukca.pdf | /aasx/files/ukca.pdf |
| ✓ | retained: `AssetSpecificProperties.GuidelineSpecificProperties[0].GuidelineForConformityDeclaration` | 2014/30/EU | 2014/30/EU |
| ✓ | retained: `AssetSpecificProperties.GuidelineSpecificProperties[0].EmissionClass` | Class A | Class A |
| ✓ | retained: `AssetSpecificProperties.GuidelineSpecificProperties[1].GuidelineForConformityDeclaration` | 2014/35/EU | 2014/35/EU |
| ✓ | retained: `AssetSpecificProperties.GuidelineSpecificProperties[1].RatedVoltage` | 24 V DC | 24 V DC |
| ✓ | retained: `AssetSpecificProperties.ProtectionClass` | IP20 | IP20 |
| ✓ | retained: `ManufacturerProductType` | EX-100-200 Compact | EX-100-200 Compact |
| ✓ | retained: `OrderCodeOfManufacturer` | EX100200 | EX100200 |
| ✓ | retained: `ProductArticleNumberOfManufacturer` | EX-100-200-A | EX-100-200-A |
| ✓ | retained: `HardwareVersion` | Rev. 2.1 | Rev. 2.1 |
| ✓ | retained: `FirmwareVersion` | 4.0.3 | 4.0.3 |
| ✓ | retained: `SoftwareVersion` | 4.0.3 | 4.0.3 |
| ✓ | retained: `InternalInventoryNumber` | INV-2024-0815 | INV-2024-0815 |
| ✓ | retained: `AddressInformation.Street` | [{'language': 'en', 'text': 'Examplestreet 1'}] | [{'language': 'en', 'text': 'Examplestreet 1'}] |
| ✓ | retained: `AddressInformation.Zipcode` | [{'language': 'en', 'text': '12345'}] | [{'language': 'en', 'text': '12345'}] |
| ✓ | retained: `AddressInformation.CityTown` | [{'language': 'en', 'text': 'Exampletown'}] | [{'language': 'en', 'text': 'Exampletown'}] |
| ✓ | retained: `AddressInformation.NationalCode` | [{'language': 'en', 'text': 'DE'}] | [{'language': 'en', 'text': 'DE'}] |
| ✓ | retained: `AddressInformation.Company` | [{'language': 'en', 'text': 'Example Manufacturer GmbH'}] | [{'language': 'en', 'text': 'Example Manufacturer GmbH'}] |
| ✓ | control: `InternalInventoryNumber → InternalInventoryNumber` | unchanged | unchanged |
| ✓ | control: `AssetSpecificProperties.ProtectionClass → AssetSpecificProperties.ProtectionClass` | unchanged | unchanged |
| ✓ | control: `AssetSpecificProperties.GuidelineSpecificProperties01.EmissionClass → AssetSpecificProperties.GuidelineSpecificProperties[0].EmissionClass` | unchanged | unchanged |
| ✓ | control: `AssetSpecificProperties.GuidelineSpecificProperties02.RatedVoltage → AssetSpecificProperties.GuidelineSpecificProperties[1].RatedVoltage` | unchanged | unchanged |

## V5: Digital Nameplate ZVEI 1.0 -> IDTA 3.0 via two records — passed

Requirements R3, R4. Method: demonstration.

Pass criterion: both records apply in order, and an application out of order is refused with the submodel left unchanged. The expectations are in fixtures/expected/nameplate_1.0_to_3.0.yaml.

| check | parameter | result | time |
|---|---|---|---:|
| chain applies and retains instance data |  | passed | 7.52 s |
| manual steps are reported |  | passed | 7.05 s |
| result is serialisable without new violations |  | passed | 7.42 s |
| conformance to the new template |  | passed | 11.32 s |
| no value is lost silently |  | passed | 9.01 s |
| version gap is bridged by two records |  | passed | 69.98 s |

Application to the instance (`fixtures/expected/nameplate_1.0_to_3.0.yaml`):

Notes: manual 2, removed 1, expanded 78, inserted 6, elided 1678

| | expectation | expected | observed |
|---|---|---|---|
| ✓ | retained: `SerialNumber` | SN0042 | SN0042 |
| ✓ | retained: `YearOfConstruction` | 2024 | 2024 |
| ✓ | retained: `Markings[0].MarkingName` | CE | CE |
| ✓ | retained: `Markings[0].MarkingFile` | /aasx/files/ce.pdf | /aasx/files/ce.pdf |
| ✓ | retained: `Markings[1].MarkingName` | UKCA | UKCA |
| ✓ | retained: `Markings[1].MarkingFile` | /aasx/files/ukca.pdf | /aasx/files/ukca.pdf |
| ✓ | retained: `AssetSpecificProperties.GuidelineSpecificProperties[0].GuidelineForConformityDeclaration` | 2014/30/EU | 2014/30/EU |
| ✓ | retained: `InternalInventoryNumber` | INV-2024-0815 | INV-2024-0815 |
| ✓ | retained: `AddressInformation.Street` | [{'language': 'en', 'text': 'Examplestreet 1'}] | [{'language': 'en', 'text': 'Examplestreet 1'}] |
| ✓ | retained: `AddressInformation.CityTown` | [{'language': 'en', 'text': 'Exampletown'}] | [{'language': 'en', 'text': 'Exampletown'}] |
| ✓ | retained: `AddressInformation.Phone.TelephoneNumber` | [{'language': 'en', 'text': '+49 123 4567'}] | [{'language': 'en', 'text': '+49 123 4567'}] |
| ✓ | retained: `AddressInformation.Email.EmailAddress` | info@example.com | info@example.com |
| ✓ | control: `InternalInventoryNumber → InternalInventoryNumber` | unchanged | unchanged |
| ✓ | manual: `OrderCodeOfManufacturer` | 1 | 1 |
| ✓ | manual: `URIOfTheProduct` | 1 | 1 |
| ✓ | removed: `Address.VATNumber` | 1 | 1 |
| ✓ | violation: `('VALUE_MISSING', 'OrderCodeOfManufacturer')` | 1 | 1 |
| ✓ | violation: `('VALUE_MISSING', 'URIOfTheProduct')` | 1 | 1 |

## V6: chain that cannot be resolved against the local submodel — passed

Requirements R4. Method: test.

Pass criterion: the chain is refused with a named reason, and no submodel is changed. The local submodel lacks the mandatory element GeneralInformation.ManufacturerName (cardinality One), on which the chain of Technical Data v1.2 -> v2.0 relies.

| check | parameter | result | time |
|---|---|---|---:|
| missing mandatory element is refused |  | passed | 1.20 s |
| unresolvable chain is refused |  | passed | 8.97 s |

## V7: publication without consent — passed

Requirements R4. Method: demonstration.

Pass criterion: the submodel remains unchanged between the reception of a record and the consent of the asset maintainer, while unrelated interactions continue. Since the absence of a change over an arbitrary period does not establish this property, the test interleaves interactions of the asset maintainer and requires shell and submodel to be unchanged after each of them.

| check | parameter | result | time |
|---|---|---|---:|
| no change before consent |  | passed | 9.48 s |

## V8: TCN Submodel Template v0.3 -> v0.4 — passed

Requirements R1, R2, R3. Method: analysis, demonstration.

Pass criterion: as V1 for the template, and as V3 for a TCN submodel v0.3 holding one record (fixtures/expected/tcn_0.3_to_0.4.yaml). The template transition has no change log, so no undocumented differences are listed.

| check | parameter | result | time |
|---|---|---|---:|
| chain reproduces target template |  | passed | 1.36 s |
| result is metamodel conformant as published |  | passed | 1.38 s |
| relocations and links are stated by hand |  | passed | 0.44 s |
| undocumented differences are enumerated |  | passed | 1.44 s |
| chain applies and retains instance data |  | passed | 2.96 s |
| manual steps are reported |  | passed | 2.99 s |
| result is serialisable without new violations |  | passed | 2.54 s |
| conformance to the new template |  | passed | 2.98 s |
| no value is lost silently |  | passed | 2.43 s |
| migrated record states the same chain |  | passed | 5.60 s |

Application to the instance (`fixtures/expected/tcn_0.3_to_0.4.yaml`):

Notes: manual 7, removed 2, transferred 1, expanded 47, elided 714

| | expectation | expected | observed |
|---|---|---|---|
| ✓ | retained: `TCNGroups[0].TCNRecords[0].NotificationId` | urn:uuid:00000000-0000-4000-8000-000000000003 | urn:uuid:00000000-0000-4000-8000-000000000003 |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].PreVersion` | https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2 | https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2 |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].PostVersion` | https://admin-shell.io/idta/SubmodelTemplate/TechnicalData/2/0 | https://admin-shell.io/idta/SubmodelTemplate/TechnicalData/2/0 |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].ChangeOperation` | UpdateIdShort | UpdateIdShort |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.NewIdShort` | CompanyLogo | CompanyLogo |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[1].ChangeOperation` | UpdateAttr | UpdateAttr |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[1].OperationArguments.AttributeKey` | typeValueListElement | typeValueListElement |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[2].ChangeOperation` | Sync | Sync |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[2].OperationArguments.TransferFunction.Kind` | Identity | Identity |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[3].ChangeOperation` | UpdateParent | UpdateParent |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.ElementPath` | https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2::GeneralInformation.ManufacturerLogo | https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2::GeneralInformation.ManufacturerLogo |
| ✓ | retained: `TCNGroups[0].TCNRecords[0].ItemsOfChange[1].OperationArguments.AttributeValue` | SubmodelElementCollection | SubmodelElementCollection |
| ✓ | retained: `InternalNote` | migrated from the MCN prototype | migrated from the MCN prototype |
| ✓ | control: `InternalNote → InternalNote` | unchanged | unchanged |
| ✓ | manual: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.AttributeValue` | 1 | 1 |
| ✓ | manual: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.ElementPath` | 1 | 3 |
| ✓ | manual: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.NewParentPath` | 1 | 1 |
| ✓ | manual: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.SourceElementPaths[0]` | 1 | 1 |
| ✓ | manual: `TCNGroups[0].TCNRecords[0].ItemsOfChange[0].OperationArguments.TargetElementPaths[0]` | 1 | 1 |
| ✓ | removed: `MCNGroups[0].MCNRecords[0].ReasonsOfChange[0].ReasonClassificationSystem` | 1 | 1 |
| ✓ | removed: `MCNGroups[0].MCNRecords[0].ReasonsOfChange[0].ReasonId` | 1 | 1 |
